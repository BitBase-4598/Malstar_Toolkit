from datetime import datetime

from fastapi import APIRouter, Depends, Request

from db import IntegrityError, get_connection
from logging_util import audit
from services.leave import (
    build_leave_export,
    ensure_leave_people,
    leave_change_summary,
    leave_to_dict,
    list_leave_plans_for_month,
    parse_leave_payload,
)
from util import now_stamp
from webutil import attachment, json_dict, query_int, respond

router = APIRouter()


@router.get("/api/leave-people")
def list_leave_people_route():
    return respond({"success": True, "data": ensure_leave_people()})


def _year_month(request: Request):
    now = datetime.now()
    year = query_int(request, "year", now.year) or now.year
    month = query_int(request, "month", now.month) or now.month
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        return None, None, respond({"success": False, "message": "Invalid year or month."}, 400)
    return year, month, None


@router.get("/api/leave-plans")
def list_leave_plans(request: Request):
    year, month, error = _year_month(request)
    if error:
        return error
    return respond({"success": True, "data": list_leave_plans_for_month(year, month)})


@router.get("/api/leave-plans/export")
def export_leave_plans(request: Request):
    year, month, error = _year_month(request)
    if error:
        return error
    buffer, filename = build_leave_export(year, month)
    audit("leave.export", summary=f"{year}-{month:02d}")
    return attachment(
        buffer,
        filename,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.post("/api/leave-plans")
def create_leave_plan(payload: dict = Depends(json_dict)):
    payload, error = parse_leave_payload(payload)
    if error:
        audit("leave.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    stamp = now_stamp()
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO LeavePlans (LeaveDate, Person, LeaveType, Status, Remark, CreatedAt, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["leaveDate"],
                    payload["person"],
                    payload["leaveType"],
                    payload["status"],
                    payload["remark"],
                    stamp,
                    stamp,
                ),
            )
            row = conn.execute("SELECT * FROM LeavePlans WHERE ID=?", (cur.lastrowid,)).fetchone()
    except IntegrityError:
        message = "This person already has a leave plan on that day."
        audit("leave.create", "failure", summary=message)
        return respond({"success": False, "message": message}, 409)
    audit(
        "leave.create",
        resource_id=row["ID"],
        summary=leave_change_summary(payload),
        extra={
            "person": payload["person"],
            "leaveType": payload["leaveType"],
            "status": payload["status"],
            "leaveDate": payload["leaveDate"],
        },
    )
    return respond({"success": True, "message": "Leave plan saved", "data": leave_to_dict(row)}, 201)


@router.put("/api/leave-plans/{plan_id}")
def update_leave_plan(plan_id: int, payload: dict = Depends(json_dict)):
    payload, error = parse_leave_payload(payload)
    if error:
        audit("leave.update", "failure", resource_id=plan_id, summary=error)
        return respond({"success": False, "message": error}, 400)
    try:
        with get_connection() as conn:
            existing = conn.execute("SELECT ID FROM LeavePlans WHERE ID=?", (plan_id,)).fetchone()
            if not existing:
                audit("leave.update", "failure", resource_id=plan_id, summary="not found")
                return respond({"success": False, "message": "Leave plan not found"}, 404)
            conn.execute(
                """
                UPDATE LeavePlans
                SET LeaveDate=?, Person=?, LeaveType=?, Status=?, Remark=?, UpdatedAt=?
                WHERE ID=?
                """,
                (
                    payload["leaveDate"],
                    payload["person"],
                    payload["leaveType"],
                    payload["status"],
                    payload["remark"],
                    now_stamp(),
                    plan_id,
                ),
            )
            row = conn.execute("SELECT * FROM LeavePlans WHERE ID=?", (plan_id,)).fetchone()
    except IntegrityError:
        message = "This person already has a leave plan on that day."
        audit("leave.update", "failure", resource_id=plan_id, summary=message)
        return respond({"success": False, "message": message}, 409)
    audit(
        "leave.update",
        resource_id=plan_id,
        summary=leave_change_summary(payload),
        extra={
            "person": payload["person"],
            "leaveType": payload["leaveType"],
            "status": payload["status"],
            "leaveDate": payload["leaveDate"],
        },
    )
    return respond({"success": True, "message": "Leave plan saved", "data": leave_to_dict(row)})


@router.delete("/api/leave-plans/{plan_id}")
def delete_leave_plan(plan_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT Person, LeaveDate, LeaveType, Status FROM LeavePlans WHERE ID=?",
            (plan_id,),
        ).fetchone()
        if not row:
            audit("leave.delete", "failure", resource_id=plan_id, summary="not found")
            return respond({"success": False, "message": "Leave plan not found"}, 404)
        conn.execute("DELETE FROM LeavePlans WHERE ID=?", (plan_id,))
    deleted = {
        "person": row["Person"],
        "leaveDate": row["LeaveDate"],
        "leaveType": row["LeaveType"],
        "status": row["Status"],
    }
    audit(
        "leave.delete",
        resource_id=plan_id,
        summary=leave_change_summary(deleted),
        extra=deleted,
    )
    return respond({"success": True, "message": "Leave plan deleted"})
