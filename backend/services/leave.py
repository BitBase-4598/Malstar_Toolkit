from datetime import datetime

LEAVE_TYPES = {"annual", "sick", "wfh", "other"}
LEAVE_STATUSES = {"planned", "confirmed"}


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
    leave_type = str(data.get("leaveType") or "annual").strip().lower()
    status = str(data.get("status") or "planned").strip().lower()
    if not person:
        return None, "Person is required."
    try:
        datetime.strptime(leave_date, "%Y-%m-%d")
    except ValueError:
        return None, "A valid leave date is required."
    if leave_type not in LEAVE_TYPES:
        return None, "Leave type must be annual, sick, WFH, or other."
    if status not in LEAVE_STATUSES:
        return None, "Status must be planned or confirmed."
    return {
        "person": person[:120],
        "leaveDate": leave_date,
        "leaveType": leave_type,
        "status": status,
    }, None
