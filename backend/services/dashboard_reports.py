import re
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER, SMTP_USE_TLS
from db import get_connection
from services.dashboard_analytics import build_dashboard_payload

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def smtp_configured():
    return bool(SMTP_HOST and SMTP_FROM)


def _blank_schedule():
    return {
        "dailyEnabled": False,
        "monthlyEnabled": False,
        "sendHour": 8,
        "recipients": "",
        "lastDailySent": "",
        "lastMonthlySent": "",
        "smtpConfigured": smtp_configured(),
    }


def _schedule_from_row(row):
    if row is None:
        return _blank_schedule()
    return {
        "dailyEnabled": bool(row["DailyEnabled"]),
        "monthlyEnabled": bool(row["MonthlyEnabled"]),
        "sendHour": int(row["SendHour"]),
        "recipients": row["Recipients"] or "",
        "lastDailySent": row["LastDailySent"] or "",
        "lastMonthlySent": row["LastMonthlySent"] or "",
        "smtpConfigured": smtp_configured(),
    }


def ensure_schedule_row(conn):
    conn.execute(
        "INSERT INTO DashboardReportSchedule (ID) VALUES (1) ON CONFLICT(ID) DO NOTHING"
    )


def get_schedule(conn):
    ensure_schedule_row(conn)
    row = conn.execute("SELECT * FROM DashboardReportSchedule WHERE ID = 1").fetchone()
    return _schedule_from_row(row)


def parse_recipients(text):
    emails = []
    for part in re.split(r"[,;\s]+", str(text or "").strip()):
        if not part:
            continue
        if not EMAIL_RE.match(part):
            raise ValueError(f"Invalid email: {part}")
        if part not in emails:
            emails.append(part)
    return emails


def save_schedule(conn, payload):
    daily = bool(payload.get("dailyEnabled"))
    monthly = bool(payload.get("monthlyEnabled"))
    try:
        hour = int(payload.get("sendHour", 8))
    except (TypeError, ValueError) as error:
        raise ValueError("Send hour must be 0–23.") from error
    if hour < 0 or hour > 23:
        raise ValueError("Send hour must be 0–23.")
    emails = parse_recipients(payload.get("recipients"))
    if (daily or monthly) and not emails:
        raise ValueError("Add at least one recipient.")
    ensure_schedule_row(conn)
    conn.execute(
        """
        UPDATE DashboardReportSchedule
        SET DailyEnabled = ?, MonthlyEnabled = ?, SendHour = ?, Recipients = ?
        WHERE ID = 1
        """,
        (int(daily), int(monthly), hour, ", ".join(emails)),
    )
    return get_schedule(conn)


def period_for(cadence, now):
    if cadence == "daily":
        day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return day, day, f"MALSTAR Ops daily report {day}"
    if cadence == "monthly":
        first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_prev = first - timedelta(days=1)
        start = last_prev.replace(day=1).strftime("%Y-%m-%d")
        end = last_prev.strftime("%Y-%m-%d")
        return start, end, f"MALSTAR Ops monthly report {start[:7]}"
    raise ValueError("cadence must be daily or monthly.")


def report_body(payload, title):
    lines = [title, ""]
    compare = payload.get("compare") or {}
    for key, label in (("gsc", "GSC"), ("area", "Area")):
        cohort = compare.get(key) or {}
        lines.append(
            f"{label}: {cohort.get('total', 0)} bookings, "
            f"{cohort.get('conversionRate', 0)}% converted, "
            f"process {cohort.get('avgProcessLabel', '—')} "
            f"({cohort.get('avgProcessCount', 0)} rows), "
            f"wait {cohort.get('avgWaitLabel', '—')} "
            f"({cohort.get('avgWaitCount', 0)} rows)."
        )
    lines.append("")
    for item in payload.get("conclusions") or []:
        text = str(item.get("text") or "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def send_smtp(recipients, subject, body):
    if not smtp_configured():
        raise RuntimeError("SMTP is not configured. Set SMTP_HOST and SMTP_FROM.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(message)


def send_report(conn, cadence, now, sender=None):
    schedule = get_schedule(conn)
    recipients = parse_recipients(schedule["recipients"])
    if not recipients:
        raise ValueError("Add at least one recipient.")
    start, end, subject = period_for(cadence, now)
    payload = build_dashboard_payload(conn, start, end)
    body = report_body(payload, subject)
    (sender or send_smtp)(recipients, subject, body)
    return {
        "cadence": cadence,
        "subject": subject,
        "recipients": recipients,
        "dateFrom": start,
        "dateTo": end,
    }


def dispatch_due_reports(now=None, sender=None):
    now = now or datetime.now()
    sent = []
    with get_connection() as conn:
        schedule = get_schedule(conn)
        today = now.strftime("%Y-%m-%d")
        month = now.strftime("%Y-%m")
        if schedule["dailyEnabled"] and now.hour >= int(schedule["sendHour"]) and schedule["lastDailySent"] != today:
            sent.append(send_report(conn, "daily", now, sender))
            conn.execute(
                "UPDATE DashboardReportSchedule SET LastDailySent = ? WHERE ID = 1",
                (today,),
            )
        if (
            schedule["monthlyEnabled"]
            and now.day == 1
            and now.hour >= int(schedule["sendHour"])
            and schedule["lastMonthlySent"] != month
        ):
            sent.append(send_report(conn, "monthly", now, sender))
            conn.execute(
                "UPDATE DashboardReportSchedule SET LastMonthlySent = ? WHERE ID = 1",
                (month,),
            )
    return sent
