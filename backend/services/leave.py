from datetime import datetime

from config import GCA_XLSX_PATH
from db import get_connection

LEAVE_TYPES = {"annual", "sick", "wfh", "half_day", "other"}
LEAVE_STATUSES = {"planned", "confirmed"}
LEAVE_TYPE_LABELS = {
    "annual": "Annual",
    "sick": "Sick",
    "wfh": "WFH",
    "half_day": "Half day",
    "other": "Other",
}
LEAVE_PEOPLE_EXCLUDE = {"jeff yang", "ailsa he"}
LEAVE_PEOPLE_EXTRA = ({"email": "", "name": "Jane Li"},)


def leave_to_dict(row):
    return {
        "id": row["ID"],
        "leaveDate": row["LeaveDate"],
        "person": row["Person"],
        "leaveType": row["LeaveType"],
        "status": row["Status"],
        "createdAt": row["CreatedAt"],
        "updatedAt": row["UpdatedAt"],
    }


def parse_leave_payload(data):
    person = str(data.get("person") or "").strip()
    leave_date = str(data.get("leaveDate") or data.get("date") or "").strip()
    leave_type = str(data.get("leaveType") or "annual").strip().lower().replace(" ", "_")
    status = str(data.get("status") or "planned").strip().lower()
    if not person:
        return None, "Person is required."
    try:
        datetime.strptime(leave_date, "%Y-%m-%d")
    except ValueError:
        return None, "A valid leave date is required."
    if leave_type in ("halfday", "half-day"):
        leave_type = "half_day"
    if leave_type not in LEAVE_TYPES:
        return None, "Leave type must be annual, sick, WFH, half day, or other."
    if status not in LEAVE_STATUSES:
        return None, "Status must be planned or confirmed."
    return {
        "person": person[:120],
        "leaveDate": leave_date,
        "leaveType": leave_type,
        "status": status,
    }, None


def leave_change_summary(payload):
    kind = LEAVE_TYPE_LABELS.get(payload.get("leaveType"), payload.get("leaveType") or "")
    status = str(payload.get("status") or "").strip()
    return f"{payload['person']} · {kind} · {status} · {payload['leaveDate']}"


def apply_people_overrides(people):
    filtered = []
    seen = set()
    for item in people or []:
        name = str(item.get("name") or "").strip()
        if not name or name.casefold() in LEAVE_PEOPLE_EXCLUDE:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        filtered.append({"email": str(item.get("email") or "").strip(), "name": name[:120]})
    for extra in LEAVE_PEOPLE_EXTRA:
        key = extra["name"].casefold()
        if key not in seen:
            seen.add(key)
            filtered.append({"email": extra["email"], "name": extra["name"]})
    filtered.sort(key=lambda item: item["name"].casefold())
    return filtered


def person_to_dict(row):
    return {
        "id": row["ID"],
        "email": row["Email"],
        "name": row["Name"],
    }


def parse_name_mapping_rows(raw_rows):
    from services.gca import cell_text

    people = []
    seen = set()
    for item in raw_rows:
        name = cell_text(item.get("name"))
        email = cell_text(item.get("email"))
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        people.append({"email": email, "name": name[:120]})
    return people


def replace_leave_people(people):
    people = apply_people_overrides(people)
    with get_connection() as conn:
        conn.execute("DELETE FROM LeavePeople")
        conn.executemany(
            "INSERT INTO LeavePeople (Email, Name) VALUES (?, ?)",
            [(item["email"], item["name"]) for item in people],
        )
    return people


def replace_leave_people_from_workbook(data):
    from io import BytesIO

    from openpyxl import load_workbook

    from services.gca import NAME_MAPPING_HEADERS, NAME_MAPPING_SHEET, read_sheet_rows

    if not data:
        return None, "No file was uploaded."
    try:
        workbook = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception:
        return None, "The file is not a valid Excel workbook."
    try:
        rows, error = read_sheet_rows(workbook, NAME_MAPPING_SHEET, NAME_MAPPING_HEADERS)
    finally:
        workbook.close()
    if error:
        return None, error
    people = apply_people_overrides(parse_name_mapping_rows(rows))
    if not people:
        return None, "Name Mapping sheet has no people."
    replace_leave_people(people)
    return {"count": len(people)}, None


def list_leave_people(conn=None):
    def fetch(db):
        rows = db.execute("SELECT * FROM LeavePeople ORDER BY LOWER(Name), ID").fetchall()
        return apply_people_overrides([person_to_dict(row) for row in rows])

    if conn is not None:
        return fetch(conn)
    with get_connection() as db:
        return fetch(db)


def ensure_leave_people():
    people = list_leave_people()
    if people:
        return people
    path = GCA_XLSX_PATH
    if path.is_file():
        result, error = replace_leave_people_from_workbook(path.read_bytes())
        if not error:
            return list_leave_people()
    return people
