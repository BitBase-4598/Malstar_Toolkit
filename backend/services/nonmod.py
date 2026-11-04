"""Non-Mod workbook snapshots, stored apart from DashboardBookings.

An upload replaces every row for one report date. That date is the optional
form value, otherwise the first YYYY-MM-DD in the filename, otherwise the most
common Date-column value (the latest date wins a tie). ``/latest`` is the
snapshot with the newest report date.
"""

import json
import re
from collections import Counter
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from config import NONMOD_MAX_ROWS
from db import get_connection
from util import now_stamp


IDENTITY_FIELDS = (
    ("orderNumber", "Order Number", "OrderNumber", 80),
    ("shipmentNumber", "Shipment Number", "ShipmentNumber", 80),
    ("messageId", "Message Id", "MessageId", 80),
    ("reportDate", "Date", "ReportDate", 40),
    ("emailReceived", "Email Received", "EmailReceived", 40),
    ("orderStatus", "Order Status", "OrderStatus", 120),
    ("emailStatus", "Email Status", "EmailStatus", 120),
    ("handledBy", "Handled By", "HandledBy", 160),
    ("handlingTime", "Handling Time", "HandlingTime", 40),
    ("bookingConvertedTime", "Booking Converted Time", "BookingConvertedTime", 40),
    ("subject", "Subject", "Subject", 500),
    ("mailbox", "Mailbox", "Mailbox", 160),
)

_IDENTITY_BY_HEADER = {
    label.casefold(): (key, column, limit)
    for key, label, column, limit in IDENTITY_FIELDS
}
_DATE_IN_NAME = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_CHANGE_VALUE_LIMIT = 4000
_HEADER_LIMIT = 200

_EMPTY_KPI = {
    "selectedBookings": 0,
    "matchedBookings": 0,
    "unmatchedBookings": 0,
    "modifiedPct": 0.0,
    "nonModPct": 0.0,
    "byMailbox": [],
    "fieldRanking": [],
}


def parse_report_date(value):
    text = str(value or "").strip()
    if not text:
        return "", None
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None, "reportDate must be YYYY-MM-DD."
    return text, None


def _header_text(value):
    text = str(value or "").replace("\ufeff", "").replace("\u00a0", " ")
    return " ".join(text.split())


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.hour or value.minute or value.second:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return ""
        if value.is_integer():
            return format(value, ".0f")
        return format(value, "f").rstrip("0").rstrip(".")
    return str(value).replace("\u00a0", " ").replace("\ufeff", "").strip()


def _canonical_date(value):
    text = _cell_text(value)
    if not text:
        return ""
    candidate = text[:10] if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-" else text
    try:
        return datetime.strptime(candidate, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _stored_date(value):
    parsed = _canonical_date(value)
    if parsed:
        return parsed
    return _cell_text(value)[:40]


def date_from_filename(filename):
    for match in _DATE_IN_NAME.finditer(Path(filename or "").name):
        candidate = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        parsed, error = parse_report_date(candidate)
        if parsed and not error:
            return parsed
    return ""


def _mode_date(values):
    counts = Counter(value for value in values if value)
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (item[1], item[0]))[-1][0]


def _change_header(header):
    folded = header.casefold()
    if folded.endswith("__old"):
        return header[:-5].strip(), "old"
    if folded.endswith("__new"):
        return header[:-5].strip(), "new"
    return "", ""


def _parse_headers(raw_header):
    cells = [_header_text(cell) for cell in list(raw_header or ())]
    while cells and not cells[-1]:
        cells.pop()
    if not any(cells):
        return None, "The workbook has no header row."
    if any(not cell for cell in cells):
        return None, "A column header is empty."
    for cell in cells:
        if len(cell) > _HEADER_LIMIT:
            return None, f"Column {cell[:80]} is too long."

    identity = {}
    paths = []
    old_index = {}
    new_index = {}
    seen = {}
    unknown = []
    duplicates = []
    for index, cell in enumerate(cells):
        folded = cell.casefold()
        if folded in seen:
            duplicates.append(cell)
            continue
        seen[folded] = cell
        if folded in _IDENTITY_BY_HEADER:
            identity[folded] = index
            continue
        path, side = _change_header(cell)
        if side:
            if not path:
                return None, f"Column {cell} has an empty field path."
            bucket = old_index if side == "old" else new_index
            if path in bucket:
                duplicates.append(cell)
                continue
            if path not in old_index and path not in new_index:
                paths.append(path)
            bucket[path] = index
            continue
        unknown.append(cell)

    missing = [
        label for _key, label, _column, _limit in IDENTITY_FIELDS
        if label.casefold() not in identity
    ]
    problems = []
    if missing:
        problems.append("Missing required columns: " + ", ".join(missing) + ".")
    if duplicates:
        problems.append("Duplicate columns: " + ", ".join(duplicates) + ".")
    unpaired = []
    for path in paths:
        if path not in old_index:
            unpaired.append(f"{path}__old")
        if path not in new_index:
            unpaired.append(f"{path}__new")
    if unpaired:
        problems.append("Change columns must be __old/__new pairs. Missing " + ", ".join(unpaired) + ".")
    if unknown:
        shown = ", ".join(unknown[:8])
        suffix = "" if len(unknown) <= 8 else f" (+{len(unknown) - 8} more)"
        problems.append(f"Unrecognized columns: {shown}{suffix}.")
    if problems:
        return None, " ".join(problems)
    return {
        "width": len(cells),
        "identity": identity,
        "paths": paths,
        "old": old_index,
        "new": new_index,
    }, None


def _ratio(part, whole):
    if not whole:
        return 0.0
    return round(part / whole, 4)


def _row_changes(cells, spec):
    changes = {}
    matched = False
    changed_paths = []
    for path in spec["paths"]:
        old = _cell_text(cells[spec["old"][path]])[:_CHANGE_VALUE_LIMIT]
        new = _cell_text(cells[spec["new"][path]])[:_CHANGE_VALUE_LIMIT]
        changes[path] = {"old": old, "new": new}
        if old or new:
            matched = True
        if old != new and (old or new):
            changed_paths.append(path)
    return changes, matched, changed_paths


def _identity_value(key, cells, spec):
    _column_key, label, _column, limit = next(
        item for item in IDENTITY_FIELDS if item[0] == key
    )
    raw = cells[spec["identity"][label.casefold()]]
    if key == "reportDate":
        return _stored_date(raw)
    return _cell_text(raw)[:limit]


def _parse_sheet(data):
    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception:
        return None, "The file is not a readable .xlsx workbook."
    try:
        if not workbook.sheetnames:
            return None, "The workbook has no sheets."
        sheet = workbook[workbook.sheetnames[0]]
        iterator = sheet.iter_rows(values_only=True)
        header = next(iterator, None)
        spec, error = _parse_headers(header)
        if error:
            return None, error
        width = spec["width"]
        parsed_rows = []
        scanned = 0
        for sheet_row, raw in enumerate(iterator, start=2):
            scanned += 1
            if scanned > NONMOD_MAX_ROWS:
                return None, f"Workbook is limited to {NONMOD_MAX_ROWS} rows."
            cells = list(raw or ())
            if len(cells) < width:
                cells.extend([None] * (width - len(cells)))
            else:
                cells = cells[:width]
            if not any(_cell_text(cell) for cell in cells):
                continue
            changes, matched, changed_paths = _row_changes(cells, spec)
            identity = {
                key: _identity_value(key, cells, spec)
                for key, _label, _column, _limit in IDENTITY_FIELDS
            }
            parsed_rows.append({
                "sheetRow": sheet_row,
                "identity": identity,
                "matched": matched,
                "changes": changes,
                "changedPaths": changed_paths,
                "parsedDate": _canonical_date(cells[spec["identity"]["date"]]),
            })
        if not parsed_rows:
            return None, "The workbook contains no data rows."
        return {"spec": spec, "rows": parsed_rows}, None
    finally:
        workbook.close()


def compute_kpis(rows, paths):
    selected = len(rows)
    matched = sum(1 for row in rows if row["matched"])
    unmatched = selected - matched
    mailbox_counts = {}
    ranking = {path: 0 for path in paths}
    for row in rows:
        mailbox = row["identity"]["mailbox"]
        bucket = mailbox_counts.setdefault(mailbox, {"mailbox": mailbox, "count": 0, "matched": 0})
        bucket["count"] += 1
        if row["matched"]:
            bucket["matched"] += 1
        for path in row["changedPaths"]:
            ranking[path] = ranking.get(path, 0) + 1
    by_mailbox = sorted(
        mailbox_counts.values(),
        key=lambda item: (-item["count"], item["mailbox"].casefold()),
    )
    field_ranking = [
        {"path": path, "count": count}
        for path, count in ranking.items()
        if count
    ]
    field_ranking.sort(key=lambda item: (-item["count"], item["path"].casefold()))
    return {
        "selectedBookings": selected,
        "matchedBookings": matched,
        "unmatchedBookings": unmatched,
        "modifiedPct": _ratio(matched, selected),
        "nonModPct": _ratio(unmatched, selected),
        "byMailbox": by_mailbox,
        "fieldRanking": field_ranking,
    }


def _resolve_report_date(explicit, filename, rows):
    if explicit:
        return explicit
    named = date_from_filename(filename)
    if named:
        return named
    return _mode_date(row["parsedDate"] for row in rows)


def _snapshot_data(upload, kpi):
    return {
        "meta": {
            "filename": upload["Filename"],
            "uploadedAt": upload["UploadedAt"],
            "reportDate": upload["ReportDate"],
            "rowCount": upload["RowCount"],
        },
        **kpi,
    }


def _load_kpi(upload):
    try:
        kpi = json.loads(upload["KpiJson"] or "{}")
    except json.JSONDecodeError:
        kpi = {}
    loaded = dict(_EMPTY_KPI)
    if isinstance(kpi, dict):
        for key in _EMPTY_KPI:
            if key in kpi:
                loaded[key] = kpi[key]
    return loaded


def _row_insert(upload_id, row):
    identity = row["identity"]
    return (
        upload_id,
        row["sheetRow"],
        identity["orderNumber"],
        identity["shipmentNumber"],
        identity["messageId"],
        identity["reportDate"],
        identity["emailReceived"],
        identity["orderStatus"],
        identity["emailStatus"],
        identity["handledBy"],
        identity["handlingTime"],
        identity["bookingConvertedTime"],
        identity["subject"],
        identity["mailbox"],
        1 if row["matched"] else 0,
        json.dumps(row["changes"], ensure_ascii=False),
    )


def _replace_snapshot(report_date, filename, rows, kpi):
    stamp = now_stamp()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT ID FROM NonModUploads WHERE ReportDate=?",
            (report_date,),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM NonModRows WHERE UploadID=?", (existing["ID"],))
            conn.execute("DELETE FROM NonModUploads WHERE ID=?", (existing["ID"],))
        cursor = conn.execute(
            """
            INSERT INTO NonModUploads (Filename, UploadedAt, ReportDate, RowCount, KpiJson)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                filename[:200],
                stamp,
                report_date,
                len(rows),
                json.dumps(kpi, ensure_ascii=False),
            ),
        )
        upload_id = cursor.lastrowid
        conn.executemany(
            """
            INSERT INTO NonModRows (
                UploadID, RowIndex, OrderNumber, ShipmentNumber, MessageId, ReportDate,
                EmailReceived, OrderStatus, EmailStatus, HandledBy, HandlingTime,
                BookingConvertedTime, Subject, Mailbox, Matched, ChangesJson
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_row_insert(upload_id, row) for row in rows],
        )
        upload = conn.execute(
            "SELECT * FROM NonModUploads WHERE ID=?",
            (upload_id,),
        ).fetchone()
    return _snapshot_data(upload, kpi)


def import_nonmod_workbook(filename, data, report_date=""):
    name = Path(filename or "").name
    if Path(name).suffix.lower() != ".xlsx":
        return None, "Upload an .xlsx workbook."
    explicit, error = parse_report_date(report_date)
    if error:
        return None, error
    if not data:
        return None, "The file is empty."
    parsed, error = _parse_sheet(data)
    if error:
        return None, error
    resolved = _resolve_report_date(explicit, name, parsed["rows"])
    if not resolved:
        return None, (
            "Could not determine reportDate. Pass reportDate or include a YYYY-MM-DD "
            "in the filename or Date column."
        )
    kpi = compute_kpis(parsed["rows"], parsed["spec"]["paths"])
    snapshot = _replace_snapshot(resolved, name, parsed["rows"], kpi)
    matched = kpi["matchedBookings"]
    unmatched = kpi["unmatchedBookings"]
    message = (
        f"Imported {kpi['selectedBookings']} bookings for {resolved} "
        f"({matched} matched, {unmatched} unmatched)."
    )
    return {"message": message, "data": snapshot}, None


def _upload_by_date(conn, report_date):
    if report_date:
        return conn.execute(
            "SELECT * FROM NonModUploads WHERE ReportDate=?",
            (report_date,),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM NonModUploads ORDER BY ReportDate DESC, ID DESC LIMIT 1"
    ).fetchone()


def latest_snapshot():
    with get_connection() as conn:
        upload = _upload_by_date(conn, "")
    if not upload:
        return {"meta": None, **_EMPTY_KPI}
    return _snapshot_data(upload, _load_kpi(upload))


def snapshot_for_date(report_date):
    parsed, error = parse_report_date(report_date)
    if error:
        return None, error
    with get_connection() as conn:
        upload = _upload_by_date(conn, parsed)
    if parsed and not upload:
        return None, "No Non-Mod snapshot for that report date."
    if not upload:
        return {"upload": None, "kpi": dict(_EMPTY_KPI)}, None
    return {"upload": upload, "kpi": _load_kpi(upload)}, None


BLANK_MAILBOX = "(blank)"


def _mailbox_filter(mailbox):
    """Return a SQL fragment applied before pagination.

    Missing or blank means every mailbox. ``(blank)`` matches rows stored
    with an empty mailbox, the same sentinel the dashboard uses.
    """
    if mailbox is None:
        return "", []
    text = str(mailbox).strip()
    if not text:
        return "", []
    if text == BLANK_MAILBOX:
        return " AND Mailbox = ?", [""]
    return " AND Mailbox = ?", [text[:160]]


def list_rows(report_date="", page=1, page_size=50, mailbox=None):
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 50), 1), 10000)
    found, error = snapshot_for_date(report_date)
    if error:
        return None, error
    upload = found["upload"]
    if not upload:
        return {
            "data": [],
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": 0,
                "totalPages": 1,
            },
        }, None
    clause, params = _mailbox_filter(mailbox)
    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM NonModRows WHERE UploadID=?{clause}",
            (upload["ID"], *params),
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM NonModRows
            WHERE UploadID=?{clause}
            ORDER BY RowIndex, ID
            LIMIT ? OFFSET ?
            """,
            (upload["ID"], *params, page_size, (page - 1) * page_size),
        ).fetchall()
    return {
        "data": [_row_to_dict(row) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
    }, None


def field_ranking(report_date=""):
    found, error = snapshot_for_date(report_date)
    if error:
        return None, error
    upload = found["upload"]
    if not upload:
        return {"reportDate": "", "fieldRanking": []}, None
    return {
        "reportDate": upload["ReportDate"],
        "fieldRanking": list(found["kpi"].get("fieldRanking") or []),
    }, None


def _row_to_dict(row):
    try:
        changes = json.loads(row["ChangesJson"] or "{}")
    except json.JSONDecodeError:
        changes = {}
    if not isinstance(changes, dict):
        changes = {}
    payload = {"id": row["ID"]}
    for key, _label, column, _limit in IDENTITY_FIELDS:
        payload[key] = row[column]
    payload["matched"] = bool(row["Matched"])
    payload["changes"] = changes
    return payload
