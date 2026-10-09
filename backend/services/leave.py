from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import GCA_XLSX_PATH
from db import get_connection

LEAVE_TYPES = {"annual", "sick", "wfh", "half_day", "on_duty", "other"}
LEAVE_STATUSES = {"planned", "confirmed"}
LEAVE_TYPE_LABELS = {
    "annual": "Annual",
    "sick": "Sick",
    "wfh": "WFH",
    "half_day": "Half day",
    "on_duty": "On duty",
    "other": "Other",
}
LEAVE_PEOPLE = (
    "Andrew Li",
    "Jane Li",
    "Jason Zhong",
    "Mina Xiang",
    "Nathan Li",
    "Nicole Jiang",
    "Qing Huang",
    "Tao Liu",
    "Wenjie Yan",
    "Yolanda Feng",
)
LEAVE_PEOPLE_EXCLUDE = {"jeff yang", "ailsa he"}


def leave_to_dict(row):
    return {
        "id": row["ID"],
        "leaveDate": row["LeaveDate"],
        "person": row["Person"],
        "leaveType": row["LeaveType"],
        "status": row["Status"],
        "remark": row["Remark"] if "Remark" in row.keys() else "",
        "createdAt": row["CreatedAt"],
        "updatedAt": row["UpdatedAt"],
    }


def parse_leave_payload(data):
    person = str(data.get("person") or "").strip()
    leave_date = str(data.get("leaveDate") or data.get("date") or "").strip()
    leave_type = str(data.get("leaveType") or "annual").strip().lower().replace(" ", "_")
    status = str(data.get("status") or "planned").strip().lower()
    remark = str(data.get("remark") or "").replace("\r\n", "\n").replace("\r", "\n")
    remark = "\n".join(line.rstrip() for line in remark.split("\n")).strip()
    if not person:
        return None, "Person is required."
    try:
        datetime.strptime(leave_date, "%Y-%m-%d")
    except ValueError:
        return None, "A valid leave date is required."
    if leave_type in ("halfday", "half-day"):
        leave_type = "half_day"
    if leave_type in ("onduty", "on-duty"):
        leave_type = "on_duty"
    if leave_type not in LEAVE_TYPES:
        return None, "Leave type must be annual, sick, WFH, half day, on duty, or other."
    if status not in LEAVE_STATUSES:
        return None, "Status must be planned or confirmed."
    return {
        "person": person[:120],
        "leaveDate": leave_date,
        "leaveType": leave_type,
        "status": status,
        "remark": remark[:500],
    }, None


def month_bounds(year, month):
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def list_leave_plans_for_month(year, month):
    start, end = month_bounds(year, month)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM LeavePlans
            WHERE LeaveDate >= ? AND LeaveDate < ?
            ORDER BY LeaveDate, LOWER(Person), ID
            """,
            (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
        ).fetchall()
    return [leave_to_dict(row) for row in rows]


def build_leave_export(year, month):
    people = [item["name"] for item in ensure_leave_people()]
    plans = list_leave_plans_for_month(year, month)
    days = (month_bounds(year, month)[1] - month_bounds(year, month)[0]).days
    title = datetime(year, month, 1).strftime("%B %Y")
    by_person_date = {}
    for plan in plans:
        key = (plan["person"].casefold(), plan["leaveDate"])
        label = LEAVE_TYPE_LABELS.get(plan["leaveType"], plan["leaveType"] or "")
        if plan.get("remark"):
            label = f"{label}: {plan['remark']}"
        by_person_date[key] = label

    workbook = Workbook()
    calendar = workbook.active
    calendar.title = "Calendar"
    calendar["A1"] = f"Leave Forecast · {title}"
    calendar["A1"].font = Font(bold=True, size=14)
    calendar.merge_cells(start_row=1, start_column=1, end_row=1, end_column=days + 1)
    calendar.cell(2, 1, "Person")
    for day in range(1, days + 1):
        cell = calendar.cell(2, day + 1, day)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    header_fill = PatternFill("solid", fgColor="D6EAF8")
    for col in range(1, days + 2):
        calendar.cell(2, col).fill = header_fill
    duty_fill = PatternFill("solid", fgColor="EFE7FB")
    for row_index, name in enumerate(people, start=3):
        calendar.cell(row_index, 1, name)
        for day in range(1, days + 1):
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            value = by_person_date.get((name.casefold(), iso), "")
            cell = calendar.cell(row_index, day + 1, value)
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            if value.lower().startswith("on duty"):
                cell.fill = duty_fill
    calendar.column_dimensions["A"].width = 22
    for day in range(1, days + 1):
        calendar.column_dimensions[get_column_letter(day + 1)].width = 14
    calendar.freeze_panes = "B3"

    plans_sheet = workbook.create_sheet("Plans")
    headers = ("Date", "Person", "Type", "Status", "Remark")
    plans_sheet.append(headers)
    for cell in plans_sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    for plan in plans:
        plans_sheet.append(
            [
                plan["leaveDate"],
                plan["person"],
                LEAVE_TYPE_LABELS.get(plan["leaveType"], plan["leaveType"]),
                plan["status"],
                plan.get("remark") or "",
            ]
        )
    for index, width in enumerate((14, 22, 14, 12, 40), start=1):
        plans_sheet.column_dimensions[get_column_letter(index)].width = width
    plans_sheet.freeze_panes = "A2"

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer, f"leave-forecast-{year:04d}-{month:02d}.xlsx"


def leave_change_summary(payload):
    kind = LEAVE_TYPE_LABELS.get(payload.get("leaveType"), payload.get("leaveType") or "")
    status = str(payload.get("status") or "").strip()
    return f"{payload['person']} · {kind} · {status} · {payload['leaveDate']}"


def apply_people_overrides(people):
    by_key = {}
    for item in people or []:
        name = str(item.get("name") or "").strip()
        key = name.casefold()
        if not name or key in LEAVE_PEOPLE_EXCLUDE:
            continue
        if key not in by_key:
            by_key[key] = {"email": str(item.get("email") or "").strip(), "name": name[:120]}
    for name in LEAVE_PEOPLE:
        key = name.casefold()
        if key not in by_key:
            by_key[key] = {"email": "", "name": name}
    return sorted(by_key.values(), key=lambda item: item["name"].casefold())


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


def stored_leave_people_names():
    with get_connection() as conn:
        return [row["Name"] for row in conn.execute("SELECT Name FROM LeavePeople ORDER BY ID")]


def ensure_leave_people():
    stored = stored_leave_people_names()
    stored_keys = {name.casefold() for name in stored}
    needed = {name.casefold() for name in LEAVE_PEOPLE}
    has_excluded = bool(stored_keys & LEAVE_PEOPLE_EXCLUDE)
    if needed <= stored_keys and not has_excluded:
        return list_leave_people()
    path = GCA_XLSX_PATH
    if path.is_file():
        _result, error = replace_leave_people_from_workbook(path.read_bytes())
        if not error:
            return list_leave_people()
    if stored:
        return list_leave_people()
    replace_leave_people([{"email": "", "name": name} for name in LEAVE_PEOPLE])
    return list_leave_people()
