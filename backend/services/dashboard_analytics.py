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


# Booking creation turn time (I-E) and time usage (J-I) cleaning thresholds.
TURN_TIME_MAX_MINUTES = 2880
TIME_USAGE_MIN_FOR_TURN = 2  # strict: J-I must be >
TIME_USAGE_MAX_MINUTES = 1440
TIME_USAGE_MIN_MINUTES = 1.7


def has_complete_times(item, need_received=False):
    if parse_dash_datetime(item.get("handlingTime")) is None:
        return False
    if parse_dash_datetime(item.get("bookingConvertedTime")) is None:
        return False
    if need_received and parse_dash_datetime(item.get("emailReceived")) is None:
        return False
    return True


def is_valid_time_usage(item):
    """Booking creation time usage (J-I): converted, times complete, 1.7 ≤ J-I ≤ 1440."""
    if not is_converted_status(item.get("emailStatus")):
        return False
    if not has_complete_times(item, need_received=False):
        return False
    usage = item.get("processMinutes")
    if usage is None:
        return False
    try:
        value = float(usage)
    except (TypeError, ValueError):
        return False
    return TIME_USAGE_MIN_MINUTES <= value <= TIME_USAGE_MAX_MINUTES


def is_valid_turn_time(item):
    """Booking creation turn time (I-E): converted, E/I/J complete, 0≤I-E≤2880 and 2<J-I≤1440."""
    if not is_converted_status(item.get("emailStatus")):
        return False
    if not has_complete_times(item, need_received=True):
        return False
    turn = item.get("handleWaitMinutes")
    usage = item.get("processMinutes")
    if turn is None or usage is None:
        return False
    try:
        turn_value = float(turn)
        usage_value = float(usage)
    except (TypeError, ValueError):
        return False
    if not (0 <= turn_value <= TURN_TIME_MAX_MINUTES):
        return False
    return TIME_USAGE_MIN_FOR_TURN < usage_value <= TIME_USAGE_MAX_MINUTES


def mean_minutes(values):
    remaining = [float(value) for value in values if value is not None]
    if not remaining:
        return None
    return round(sum(remaining) / len(remaining), 1), len(remaining)


def average_process_times(items):
    return mean_minutes(
        item["processMinutes"]
        for item in items
        if is_valid_time_usage(item)
    )


def average_turn_times(items):
    return mean_minutes(
        item["handleWaitMinutes"]
        for item in items
        if is_valid_turn_time(item)
    )


BLANK_MAILBOX = "(blank)"

# Shared with frontend CASE_MAILBOXES. Match is case-insensitive.
GSC_MAILBOXES = (
    "CUSLCL.SZH@LnS.maersk.com",
    "CUSLCLEUR.SZH@LnS.maersk.com",
    "HKGLCL@LnS.maersk.com",
    "TWNLCL-CUS@LnS.maersk.com",
    "CN.BOSCH.CFSPRSEXP@lns.maersk.com",
)
GSC_MAILBOX_KEYS = {name.casefold() for name in GSC_MAILBOXES}

DEFAULT_HANDLER_ROSTER = (
    "qing.huang",
    "wenjie.yan",
    "meiling.xiang",
    "nicole.y.jiang",
    "yolanda.feng",
    "jane.l",
    "tao.l",
    "nathan.li",
    "andrew.li",
    "y.zhong",
)


def handler_key(value):
    text = str(value or "").strip()
    if not text:
        return ""
    return text.split("@", 1)[0].casefold()


def parse_handler_roster(text):
    names = []
    seen = set()
    for part in str(text or "").replace(",", "\n").splitlines():
        name = part.strip()
        key = handler_key(name)
        if not key or key in seen or "@" in name:
            continue
        seen.add(key)
        names.append(name.split("@", 1)[0])
    return names


def handler_roster(conn):
    row = conn.execute("SELECT Names FROM DashboardHandlerRoster WHERE ID = 1").fetchone()
    if row is None or not str(row["Names"] or "").strip():
        return list(DEFAULT_HANDLER_ROSTER)
    return parse_handler_roster(row["Names"])


def save_handler_roster(conn, text):
    names = parse_handler_roster(text)
    if not names:
        raise ValueError("Add at least one handler.")
    conn.execute(
        """
        INSERT INTO DashboardHandlerRoster (ID, Names) VALUES (1, ?)
        ON CONFLICT(ID) DO UPDATE SET Names = excluded.Names
        """,
        ("\n".join(names),),
    )
    return names


def is_gsc_mailbox(mailbox):
    return str(mailbox or "").strip().casefold() in GSC_MAILBOX_KEYS


def cohort_summary(items):
    """Same cleaning rules as the page KPIs, for one mailbox cohort."""
    total = len(items)
    converted = [item for item in items if is_converted_status(item.get("emailStatus"))]
    processing = [item for item in items if is_processing_status(item.get("emailStatus"))]
    missing_ship = [item for item in items if not item.get("shipmentNumber")]
    process_result = average_process_times(items)
    wait_result = average_turn_times(items)
    avg_process, process_count = process_result if process_result else (None, 0)
    avg_wait, wait_count = wait_result if wait_result else (None, 0)
    return {
        "total": total,
        "converted": len(converted),
        "conversionRate": round((len(converted) / total) * 100, 1) if total else 0,
        "processing": len(processing),
        "missingShipment": len(missing_ship),
        "avgProcessMinutes": avg_process,
        "avgProcessCount": process_count,
        "avgProcessLabel": f"{avg_process} min" if avg_process is not None else "—",
        "avgWaitMinutes": avg_wait,
        "avgWaitCount": wait_count,
        "avgWaitLabel": f"{avg_wait} min" if avg_wait is not None else "—",
    }


def short_handler_name(value):
    text = str(value or "").strip()
    if not text:
        return "unknown"
    return text.split("@", 1)[0]


def section_note(kind, section, text, keywords, period, group="", lead=""):
    return {
        "kind": kind,
        "section": section,
        "group": group,
        "lead": lead,
        "text": text,
        "keywords": [str(item) for item in keywords if item is not None and str(item) != ""],
        "period": period,
    }


def weekday_hour_peaks(items):
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    counts = {name: [0] * 24 for name in names}
    for item in items:
        received = parse_dash_datetime(item.get("emailReceived"))
        if received is None:
            continue
        counts[names[received.weekday()]][received.hour] += 1
    peaks = []
    for name in names:
        hours = counts[name]
        if not sum(hours):
            continue
        hour = max(range(24), key=lambda index: hours[index])
        peaks.append({"weekday": name, "label": f"{hour:02d}:00", "count": hours[hour]})
    return peaks


def _section_conclusions(
    period,
    items,
    selected_mailboxes,
    gsc_summary,
    area_summary,
    top_handler,
    avg_by_handler,
    by_hour,
    weekday_peaks,
    roster,
    processing,
    missing_ship,
    flagged,
):
    if not items:
        text = (
            f"No bookings for the selected mailboxes in {period}."
            if selected_mailboxes
            else f"No bookings in {period}. Upload a daily report CSV or widen the dates."
        )
        return [section_note("empty", "Overview", text, [period], period)]

    notes = []
    overview = (
        f"GSC {gsc_summary['total']} bookings, {gsc_summary['converted']} converted "
        f"({gsc_summary['conversionRate']}%), {gsc_summary['processing']} processing, "
        f"{gsc_summary['missingShipment']} missing shipment, "
        f"process {gsc_summary['avgProcessLabel']}, wait {gsc_summary['avgWaitLabel']}. "
        f"Area {area_summary['total']} bookings, {area_summary['converted']} converted "
        f"({area_summary['conversionRate']}%), {area_summary['processing']} processing, "
        f"{area_summary['missingShipment']} missing shipment, "
        f"process {area_summary['avgProcessLabel']}, wait {area_summary['avgWaitLabel']}."
    )
    notes.append(section_note(
        "overview",
        "Overview",
        overview,
        [
            "GSC",
            "Area",
            str(gsc_summary["total"]),
            str(gsc_summary["converted"]),
            f"{gsc_summary['conversionRate']}%",
            str(gsc_summary["processing"]),
            str(gsc_summary["missingShipment"]),
            gsc_summary["avgProcessLabel"],
            gsc_summary["avgWaitLabel"],
            str(area_summary["total"]),
            str(area_summary["converted"]),
            f"{area_summary['conversionRate']}%",
            str(area_summary["processing"]),
            str(area_summary["missingShipment"]),
            area_summary["avgProcessLabel"],
            area_summary["avgWaitLabel"],
        ],
        period,
        lead="GSC turned a larger share of bookings into shipments, and did it in less time than Area.",
    ))

    if top_handler:
        name = short_handler_name(top_handler["label"])
        handler_text = f"{name}, {top_handler['count']} bookings."
        handler_keys = [name, str(top_handler["count"])]
    else:
        handler_text = "No roster bookings."
        handler_keys = []
    notes.append(section_note(
        "by-handler",
        "By handler",
        handler_text,
        handler_keys,
        period,
        group="handlers",
        lead=f"Among the {len(roster)} roster handlers, one person carried the most bookings.",
    ))

    if avg_by_handler:
        slowest = avg_by_handler[0]
        slow_name = short_handler_name(slowest["label"])
        group_avg = round(sum(item["minutes"] for item in avg_by_handler) / len(avg_by_handler), 1)
        notes.append(section_note(
            "quadrant",
            "Handler quadrants",
            f"Roster process average {group_avg} min.",
            [f"{group_avg} min"],
            period,
            group="handlers",
            lead="The roster as a group is finishing converted work quickly.",
        ))
        notes.append(section_note(
            "process-by-handler",
            "Avg process-time by handler",
            f"{slow_name}, {slowest['minutes']} min.",
            [slow_name, f"{slowest['minutes']} min"],
            period,
            group="handlers",
            lead="One roster handler is taking longer than the others on average.",
        ))
    else:
        notes.append(section_note(
            "quadrant",
            "Handler quadrants",
            "No roster process times.",
            [],
            period,
            group="handlers",
            lead="There is not enough cleaned process time to place the roster.",
        ))
        notes.append(section_note(
            "process-by-handler",
            "Avg process-time by handler",
            "No cleaned roster rows.",
            [],
            period,
            group="handlers",
            lead="No roster handler has a cleaned process time in this range.",
        ))

    peak = max(by_hour, key=lambda item: item["count"]) if by_hour else None
    day_bits = [
        f"{item['weekday']} {item['label']} ({item['count']})"
        for item in weekday_peaks
    ]
    if peak and peak["count"]:
        hour_text = f"Overall {peak['label']}, {peak['count']} emails."
        if day_bits:
            hour_text += " By weekday the peaks are " + ", ".join(day_bits) + "."
        notes.append(section_note(
            "by-hour",
            "Volume by hour",
            hour_text,
            [peak["label"], str(peak["count"]), *[item["weekday"] for item in weekday_peaks], *[item["label"] for item in weekday_peaks]],
            period,
            lead="Inbound mail bunches in the morning, and the busiest hour shifts by weekday.",
        ))
    else:
        notes.append(section_note(
            "by-hour",
            "Volume by hour",
            "No parseable email times.",
            [],
            period,
            lead="There is no received time to place mail on the clock.",
        ))

    flagged_text = (
        f"{len(flagged[:40])} flagged, {len(processing)} processing, "
        f"{len(missing_ship)} missing shipment."
    )
    notes.append(section_note(
        "flagged",
        "Flagged rows",
        flagged_text,
        [str(len(flagged[:40])), str(len(processing)), str(len(missing_ship))],
        period,
        lead="Most of the abnormal rows are still open or never received a shipment number.",
    ))
    return notes


def split_gsc_area(items):
    gsc = []
    area = []
    for item in items:
        if is_gsc_mailbox(item.get("mailbox")):
            gsc.append(item)
        else:
            area.append(item)
    return gsc, area


def selected_mailbox_keys(mailbox):
    if mailbox is None:
        raw = []
    elif isinstance(mailbox, str):
        raw = [mailbox]
    else:
        raw = list(mailbox)
    selected = []
    seen = set()
    for value in raw:
        text = str(value or "").strip()[:160]
        if not text or text in seen:
            continue
        seen.add(text)
        selected.append(text)
    return selected


def build_dashboard_payload(conn, date_from="", date_to="", mailbox=""):
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
    date_items = [dashboard_row_to_dict(row) for row in rows]
    mailbox_names = sorted(
        {item["mailbox"] for item in date_items if item["mailbox"]},
        key=str.casefold,
    )
    has_blank_mailbox = any(not item["mailbox"] for item in date_items)
    selected_mailboxes = selected_mailbox_keys(mailbox)
    selected_keys = set(selected_mailboxes)
    if selected_keys:
        items = [item for item in date_items if (item["mailbox"] or BLANK_MAILBOX) in selected_keys]
    else:
        items = date_items
    total = len(items)
    converted = [item for item in items if is_converted_status(item["emailStatus"])]
    processing = [item for item in items if is_processing_status(item["emailStatus"])]
    missing_ship = [item for item in items if not item["shipmentNumber"]]
    usage_ok = [item for item in items if is_valid_time_usage(item)]
    turn_ok = [item for item in items if is_valid_turn_time(item)]
    process_neg = [
        item
        for item in items
        if item["processMinutes"] is not None and item["processMinutes"] < 0
    ]
    waits = [item["handleWaitMinutes"] for item in turn_ok]
    avg_result = average_process_times(items)
    avg_process, avg_process_count = avg_result if avg_result else (None, 0)
    max_process = None
    if usage_ok:
        max_process = max(usage_ok, key=lambda item: item["processMinutes"])
    roster = handler_roster(conn)
    roster_keys = {handler_key(name) for name in roster}
    handler_counts = {}
    handler_process = {}
    for item in items:
        key = handler_key(item.get("handledBy"))
        if key not in roster_keys:
            continue
        handler = item["handledBy"] or "(blank)"
        handler_counts[handler] = handler_counts.get(handler, 0) + 1
        if is_valid_time_usage(item):
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
    weekday_peaks = weekday_hour_peaks(items)
    avg_by_handler = []
    for name, values in handler_process.items():
        result = mean_minutes(values)
        if result is None:
            continue
        minutes, count = result
        avg_by_handler.append({
            "label": name,
            "minutes": minutes,
            "count": count,
        })
    if avg_by_handler:
        peak = max(item["minutes"] for item in avg_by_handler)
        for item in avg_by_handler:
            item["isMax"] = item["minutes"] == peak
    avg_by_handler.sort(key=lambda item: (-item["minutes"], item["label"]))

    wait_median = median_value(waits)
    wait_limit = max(60, int(wait_median * 1.5)) if wait_median is not None else 60
    wait_outliers = [
        item
        for item in turn_ok
        if item["handleWaitMinutes"] is not None and item["handleWaitMinutes"] > wait_limit
    ]
    wait_outliers.sort(key=lambda item: item["handleWaitMinutes"], reverse=True)
    slowest_wait = wait_outliers[0] if wait_outliers else None
    if not slowest_wait and turn_ok:
        slowest_wait = max(turn_ok, key=lambda item: item["handleWaitMinutes"])

    message_ids = {}
    for item in items:
        mid = item["messageId"]
        if not mid:
            continue
        message_ids.setdefault(mid, []).append(item)
    duplicates = [group for group in message_ids.values() if len(group) > 1]
    duplicate_rows = [item for group in duplicates for item in group]

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
    gsc_items, area_items = split_gsc_area(items)
    gsc_summary = cohort_summary(gsc_items)
    area_summary = cohort_summary(area_items)
    period_start = date_from or date_min or "open"
    period_end = date_to or date_max or "open"
    period = period_start if period_start == period_end else f"{period_start} to {period_end}"
    conclusions = _section_conclusions(
        period=period,
        items=items,
        selected_mailboxes=selected_mailboxes,
        gsc_summary=gsc_summary,
        area_summary=area_summary,
        top_handler=top_handler,
        avg_by_handler=avg_by_handler,
        by_hour=by_hour,
        weekday_peaks=weekday_peaks,
        roster=roster,
        processing=processing,
        missing_ship=missing_ship,
        flagged=flagged,
    )

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
            "mailboxes": mailbox_names,
            "hasBlankMailbox": has_blank_mailbox,
            "mailbox": selected_mailboxes[0] if len(selected_mailboxes) == 1 else "",
            "handlerRoster": roster,
        },
        "compare": {
            "gsc": gsc_summary,
            "area": area_summary,
        },
        "kpis": {
            "total": total,
            "converted": len(converted),
            "processing": len(processing),
            "conversionRate": round((len(converted) / total) * 100, 1) if total else 0,
            "handlers": len(handler_counts),
            "missingShipment": len(missing_ship),
            "avgProcessMinutes": avg_process,
            "avgProcessLabel": f"{avg_process} min" if avg_process is not None else "—",
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
