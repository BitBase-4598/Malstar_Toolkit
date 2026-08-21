from datetime import datetime

from config import DASHBOARD_MISSING


DASHBOARD_FIELDS = (
    ("orderNumber", "order number"),
    ("shipmentNumber", "shipment number"),
    ("messageId", "message id"),
    ("date", "date"),
    ("emailReceived", "email received"),
    ("emailStatus", "email status"),
    ("handledBy", "handled by"),
    ("handlingTime", "handling time"),
    ("bookingConvertedTime", "booking converted time"),
    ("subject", "subject"),
    ("mailbox", "mailbox"),
)


def clean_dash_value(value):
    text = str(value or "").strip()
    if text.casefold() in DASHBOARD_MISSING or text == "—":
        return ""
    return text


def parse_dash_datetime(value):
    text = clean_dash_value(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def minutes_between(start, end):
    if not start or not end:
        return None
    return int((end - start).total_seconds() // 60)


def format_minutes(value):
    if value is None:
        return ""
    minutes = int(value)
    sign = "-" if minutes < 0 else ""
    minutes = abs(minutes)
    if minutes < 60:
        return f"{sign}{minutes} min"
    hours, rest = divmod(minutes, 60)
    if rest:
        return f"{sign}{hours}h {rest}m"
    return f"{sign}{hours}h"


def parse_dashboard_record(raw):
    if not isinstance(raw, dict):
        return None, "Each row must be an object."
    data = {}
    for key, _label in DASHBOARD_FIELDS:
        data[key] = clean_dash_value(raw.get(key) or raw.get(_label) or raw.get(_label.title()) or "")
    report_date = data["date"]
    parsed_date = parse_dash_datetime(report_date)
    if parsed_date:
        report_date = parsed_date.strftime("%Y-%m-%d")
    elif report_date:
        return None, "Date must be YYYY-MM-DD."
    received = parse_dash_datetime(data["emailReceived"])
    handled = parse_dash_datetime(data["handlingTime"])
    converted = parse_dash_datetime(data["bookingConvertedTime"])
    return {
        "orderNumber": data["orderNumber"][:80],
        "shipmentNumber": data["shipmentNumber"][:80],
        "messageId": data["messageId"][:80],
        "reportDate": report_date,
        "emailReceived": received.strftime("%Y-%m-%d %H:%M:%S") if received else data["emailReceived"][:40],
        "emailStatus": data["emailStatus"][:120],
        "handledBy": data["handledBy"][:160],
        "handlingTime": handled.strftime("%Y-%m-%d %H:%M:%S") if handled else data["handlingTime"][:40],
        "bookingConvertedTime": converted.strftime("%Y-%m-%d %H:%M:%S") if converted else data["bookingConvertedTime"][:40],
        "subject": data["subject"][:500],
        "mailbox": data["mailbox"][:160],
        "handleWaitMinutes": minutes_between(received, handled),
        "processMinutes": minutes_between(handled, converted),
    }, None


def dashboard_row_to_dict(row):
    return {
        "id": row["ID"],
        "orderNumber": row["OrderNumber"],
        "shipmentNumber": row["ShipmentNumber"],
        "messageId": row["MessageId"],
        "date": row["ReportDate"],
        "emailReceived": row["EmailReceived"],
        "emailStatus": row["EmailStatus"],
        "handledBy": row["HandledBy"],
        "handlingTime": row["HandlingTime"],
        "bookingConvertedTime": row["BookingConvertedTime"],
        "subject": row["Subject"],
        "mailbox": row["Mailbox"],
        "handleWaitMinutes": row["HandleWaitMinutes"],
        "processMinutes": row["ProcessMinutes"],
    }


def is_converted_status(status):
    return "converted" in str(status or "").casefold()


def is_processing_status(status):
    return "processing" in str(status or "").casefold()


def median_value(values):
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def build_dashboard_payload(conn, date_from="", date_to=""):
    bounds = conn.execute(
        """
        SELECT MIN(ReportDate), MAX(ReportDate), COUNT(*)
        FROM DashboardBookings
        WHERE ReportDate != ''
        """
    ).fetchone()
    date_min = bounds[0] or ""
    date_max = bounds[1] or ""
    stored_count = conn.execute("SELECT COUNT(*) FROM DashboardBookings").fetchone()[0]
    meta_row = conn.execute("SELECT Filename, UploadedAt, RowCount FROM DashboardMeta WHERE ID=1").fetchone()
    clauses = []
    params = []
    if date_from:
        clauses.append("ReportDate >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("ReportDate <= ?")
        params.append(date_to)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM DashboardBookings {where} ORDER BY ReportDate, HandlingTime, ID",
        params,
    ).fetchall()
    items = [dashboard_row_to_dict(row) for row in rows]
    total = len(items)
    converted = [item for item in items if is_converted_status(item["emailStatus"])]
    processing = [item for item in items if is_processing_status(item["emailStatus"])]
    missing_ship = [item for item in items if not item["shipmentNumber"]]
    process_ok = [
        item
        for item in items
        if item["processMinutes"] is not None and item["processMinutes"] >= 0
    ]
    process_neg = [
        item
        for item in items
        if item["processMinutes"] is not None and item["processMinutes"] < 0
    ]
    waits = [
        item["handleWaitMinutes"]
        for item in items
        if item["handleWaitMinutes"] is not None
    ]
    avg_process = (
        round(sum(item["processMinutes"] for item in process_ok) / len(process_ok), 1)
        if process_ok
        else None
    )
    max_process = None
    if process_ok:
        max_process = max(process_ok, key=lambda item: item["processMinutes"])
    handler_counts = {}
    handler_process = {}
    for item in items:
        handler = item["handledBy"] or "(blank)"
        handler_counts[handler] = handler_counts.get(handler, 0) + 1
        if item["processMinutes"] is not None and item["processMinutes"] >= 0:
            handler_process.setdefault(handler, []).append(item["processMinutes"])
    by_handler = sorted(
        [{"label": name, "count": count} for name, count in handler_counts.items()],
        key=lambda item: (-item["count"], item["label"]),
    )
    top_handler = by_handler[0] if by_handler else None
    status_counts = {}
    for item in items:
        label = item["emailStatus"] or "(blank)"
        status_counts[label] = status_counts.get(label, 0) + 1
    by_status = sorted(
        [{"label": name, "count": count} for name, count in status_counts.items()],
        key=lambda item: (-item["count"], item["label"]),
    )
    hour_counts = [0] * 24
    for item in items:
        received = parse_dash_datetime(item["emailReceived"])
        if received:
            hour_counts[received.hour] += 1
    by_hour = [{"label": f"{hour:02d}:00", "count": hour_counts[hour]} for hour in range(24)]
    avg_by_handler = []
    for name, values in handler_process.items():
        avg_by_handler.append({
            "label": name,
            "minutes": round(sum(values) / len(values), 1),
            "count": len(values),
            "isMax": bool(max_process and name == (max_process["handledBy"] or "(blank)")),
        })
    avg_by_handler.sort(key=lambda item: (-item["minutes"], item["label"]))

    wait_median = median_value(waits)
    wait_limit = max(60, int(wait_median * 1.5)) if wait_median is not None else 60
    wait_outliers = [
        item
        for item in items
        if item["handleWaitMinutes"] is not None and item["handleWaitMinutes"] > wait_limit
    ]
    wait_outliers.sort(key=lambda item: item["handleWaitMinutes"], reverse=True)
    slowest_wait = wait_outliers[0] if wait_outliers else None
    if not slowest_wait:
        with_wait = [item for item in items if item["handleWaitMinutes"] is not None]
        if with_wait:
            slowest_wait = max(with_wait, key=lambda item: item["handleWaitMinutes"])

    message_ids = {}
    for item in items:
        mid = item["messageId"]
        if not mid:
            continue
        message_ids.setdefault(mid, []).append(item)
    duplicates = [group for group in message_ids.values() if len(group) > 1]
    duplicate_rows = [item for group in duplicates for item in group]

    conclusions = []
    if max_process:
        conclusions.append({
            "kind": "highest-process",
            "text": (
                f"Highest process-time is {format_minutes(max_process['processMinutes'])} "
                f"on {max_process['orderNumber'] or 'an order'} "
                f"({max_process['handledBy'] or 'unknown handler'})."
            ),
        })
    if avg_process is not None:
        conclusions.append({
            "kind": "average-process",
            "text": f"Average process-time is {format_minutes(avg_process)} across {len(process_ok)} converted bookings.",
        })
    if top_handler:
        conclusions.append({
            "kind": "highest-volume",
            "text": f"Highest volume is {top_handler['label']} with {top_handler['count']} bookings.",
        })
    if slowest_wait:
        conclusions.append({
            "kind": "slowest-wait",
            "text": (
                f"Slowest handle wait is {format_minutes(slowest_wait['handleWaitMinutes'])} "
                f"on {slowest_wait['orderNumber'] or 'an order'}."
            ),
        })
    if processing:
        conclusions.append({
            "kind": "processing",
            "text": f"{len(processing)} booking{'s' if len(processing) != 1 else ''} still processing.",
        })
    if missing_ship:
        conclusions.append({
            "kind": "missing-shipment",
            "text": f"{len(missing_ship)} row{'s' if len(missing_ship) != 1 else ''} missing a shipment number.",
        })
    if duplicates:
        conclusions.append({
            "kind": "duplicate-message",
            "text": f"{len(duplicates)} message id{'s' if len(duplicates) != 1 else ''} appear on more than one row.",
        })
    if process_neg:
        conclusions.append({
            "kind": "converted-before-handling",
            "text": f"{len(process_neg)} row{'s' if len(process_neg) != 1 else ''} have converted time before handling time.",
        })
    if wait_outliers:
        conclusions.append({
            "kind": "wait-outlier",
            "text": f"{len(wait_outliers)} handle wait{'s' if len(wait_outliers) != 1 else ''} above {format_minutes(wait_limit)}.",
        })
    if not items:
        conclusions.append({
            "kind": "empty",
            "text": "No bookings in this date range. Upload a daily report CSV or widen the dates.",
        })

    flagged_map = {}
    def flag_row(item, reason):
        current = flagged_map.get(item["id"])
        if current:
            if reason not in current["reasons"]:
                current["reasons"].append(reason)
            return
        flagged_map[item["id"]] = {**item, "reasons": [reason], "isHighestProcess": False}

    if max_process:
        flag_row(max_process, "Highest process-time")
        flagged_map[max_process["id"]]["isHighestProcess"] = True
    for item in process_neg:
        flag_row(item, "Converted before handling")
    for item in missing_ship:
        flag_row(item, "Missing shipment")
    for item in processing:
        flag_row(item, "Still processing")
    for item in duplicate_rows:
        flag_row(item, "Duplicate message id")
    for item in wait_outliers[:12]:
        flag_row(item, "Long handle wait")

    flagged = list(flagged_map.values())
    flagged.sort(key=lambda item: (not item["isHighestProcess"], -len(item["reasons"]), item["orderNumber"]))

    return {
        "meta": {
            "filename": meta_row["Filename"] if meta_row else "",
            "uploadedAt": meta_row["UploadedAt"] if meta_row else "",
            "rowCount": meta_row["RowCount"] if meta_row else stored_count,
            "filteredCount": total,
            "dateMin": date_min,
            "dateMax": date_max,
            "dateFrom": date_from or date_min,
            "dateTo": date_to or date_max,
        },
        "kpis": {
            "total": total,
            "converted": len(converted),
            "processing": len(processing),
            "conversionRate": round((len(converted) / total) * 100, 1) if total else 0,
            "handlers": len(handler_counts),
            "missingShipment": len(missing_ship),
            "avgProcessMinutes": avg_process,
            "avgProcessLabel": format_minutes(avg_process) if avg_process is not None else "—",
            "maxProcessMinutes": max_process["processMinutes"] if max_process else None,
            "maxProcessLabel": format_minutes(max_process["processMinutes"]) if max_process else "—",
            "maxProcessOrder": max_process["orderNumber"] if max_process else "",
            "maxProcessHandler": max_process["handledBy"] if max_process else "",
        },
        "series": {
            "byHandler": by_handler,
            "byStatus": by_status,
            "byHour": by_hour,
            "processByHandler": avg_by_handler,
        },
        "conclusions": conclusions,
        "flagged": flagged[:40],
        "rows": [
            {
                "id": item["id"],
                "orderNumber": item["orderNumber"],
                "shipmentNumber": item["shipmentNumber"],
                "messageId": item["messageId"],
                "date": item["date"],
                "emailReceived": item["emailReceived"],
                "emailStatus": item["emailStatus"],
                "handledBy": item["handledBy"],
                "handlingTime": item["handlingTime"],
                "bookingConvertedTime": item["bookingConvertedTime"],
                "subject": item["subject"] or "",
                "mailbox": item.get("mailbox") or "",
                "handleWaitMinutes": item["handleWaitMinutes"],
                "processMinutes": item["processMinutes"],
            }
            for item in items
        ],
    }
