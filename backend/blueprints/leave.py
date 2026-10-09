from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

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

bp = Blueprint("leave", __name__)


@bp.get("/api/leave-people")
def list_leave_people_route():
    return jsonify({"success": True, "data": ensure_leave_people()})


def _year_month():
    now = datetime.now()
    year = request.args.get("year", now.year, type=int) or now.year
    month = request.args.get("month", now.month, type=int) or now.month
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        return None, None, jsonify({"success": False, "message": "Invalid year or month."}), 400
    return year, month, None, None


@bp.get("/api/leave-plans")
def list_leave_plans():
    year, month, error, status = _year_month()
    if error:
        return error, status
    return jsonify({"success": True, "data": list_leave_plans_for_month(year, month)})


@bp.get("/api/leave-plans/export")
def export_leave_plans():
    year, month, error, status = _year_month()
    if error:
        return error, status
    buffer, filename = build_leave_export(year, month)
    audit("leave.export", summary=f"{year}-{month:02d}")
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.post("/api/leave-plans")
def create_leave_plan():
    payload, error = parse_leave_payload(request.get_json(silent=True) or {})
    if error:
        audit("leave.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
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
        return jsonify({"success": False, "message": message}), 409
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
    return jsonify({"success": True, "message": "Leave plan saved", "data": leave_to_dict(row)}), 201


@bp.put("/api/leave-plans/<int:plan_id>")
def update_leave_plan(plan_id):
    payload, error = parse_leave_payload(request.get_json(silent=True) or {})
    if error:
        audit("leave.update", "failure", resource_id=plan_id, summary=error)
        return jsonify({"success": False, "message": error}), 400
    try:
        with get_connection() as conn:
            existing = conn.execute("SELECT ID FROM LeavePlans WHERE ID=?", (plan_id,)).fetchone()
            if not existing:
                audit("leave.update", "failure", resource_id=plan_id, summary="not found")
                return jsonify({"success": False, "message": "Leave plan not found"}), 404
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
        return jsonify({"success": False, "message": message}), 409
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
    return jsonify({"success": True, "message": "Leave plan saved", "data": leave_to_dict(row)})


@bp.delete("/api/leave-plans/<int:plan_id>")
def delete_leave_plan(plan_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT Person, LeaveDate, LeaveType, Status FROM LeavePlans WHERE ID=?",
            (plan_id,),
        ).fetchone()
        if not row:
            audit("leave.delete", "failure", resource_id=plan_id, summary="not found")
            return jsonify({"success": False, "message": "Leave plan not found"}), 404
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
    return jsonify({"success": True, "message": "Leave plan deleted"})
