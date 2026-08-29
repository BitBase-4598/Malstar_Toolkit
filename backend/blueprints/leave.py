from datetime import datetime
import sqlite3

from flask import Blueprint, jsonify, request

from db import get_connection
from logging_util import audit
from services.leave import leave_to_dict, parse_leave_payload
from util import now_stamp

bp = Blueprint("leave", __name__)


@bp.get("/api/leave-plans")
def list_leave_plans():
    now = datetime.now()
    year = request.args.get("year", now.year, type=int) or now.year
    month = request.args.get("month", now.month, type=int) or now.month
    if month < 1 or month > 12 or year < 2000 or year > 2100:
        return jsonify({"success": False, "message": "Invalid year or month."}), 400
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM LeavePlans
            WHERE LeaveDate >= ? AND LeaveDate < ?
            ORDER BY LeaveDate, LOWER(Person), ID
            """,
            (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")),
        ).fetchall()
    return jsonify({"success": True, "data": [leave_to_dict(row) for row in rows]})


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
                INSERT INTO LeavePlans (LeaveDate, Person, LeaveType, Status, CreatedAt, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["leaveDate"],
                    payload["person"],
                    payload["leaveType"],
                    payload["status"],
                    stamp,
                    stamp,
                ),
            )
            row = conn.execute("SELECT * FROM LeavePlans WHERE ID=?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        message = "This person already has a leave plan on that day."
        audit("leave.create", "failure", summary=message)
        return jsonify({"success": False, "message": message}), 409
    audit(
        "leave.create",
        resource_id=row["ID"],
        summary=f"{payload['person']} {payload['leaveDate']}",
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
                SET LeaveDate=?, Person=?, LeaveType=?, Status=?, UpdatedAt=?
                WHERE ID=?
                """,
                (
                    payload["leaveDate"],
                    payload["person"],
                    payload["leaveType"],
                    payload["status"],
                    now_stamp(),
                    plan_id,
                ),
            )
            row = conn.execute("SELECT * FROM LeavePlans WHERE ID=?", (plan_id,)).fetchone()
    except sqlite3.IntegrityError:
        message = "This person already has a leave plan on that day."
        audit("leave.update", "failure", resource_id=plan_id, summary=message)
        return jsonify({"success": False, "message": message}), 409
    audit(
        "leave.update",
        resource_id=plan_id,
        summary=f"{payload['person']} {payload['leaveDate']}",
    )
    return jsonify({"success": True, "message": "Leave plan saved", "data": leave_to_dict(row)})


@bp.delete("/api/leave-plans/<int:plan_id>")
def delete_leave_plan(plan_id):
    with get_connection() as conn:
        row = conn.execute("SELECT Person, LeaveDate FROM LeavePlans WHERE ID=?", (plan_id,)).fetchone()
        if not row:
            audit("leave.delete", "failure", resource_id=plan_id, summary="not found")
            return jsonify({"success": False, "message": "Leave plan not found"}), 404
        conn.execute("DELETE FROM LeavePlans WHERE ID=?", (plan_id,))
    audit(
        "leave.delete",
        resource_id=plan_id,
        summary=f"{row['Person']} {row['LeaveDate']}",
    )
    return jsonify({"success": True, "message": "Leave plan deleted"})
