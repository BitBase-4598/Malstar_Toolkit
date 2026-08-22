import csv
import io
from datetime import datetime

from flask import Blueprint, Response, jsonify, request

from db import get_connection
from logging_util import is_key_log_action, log_event

bp = Blueprint("logs", __name__)


def activity_log_filters():
    clauses = []
    params = []
    timestamp = str(request.args.get("timestamp") or "").strip()
    action = str(request.args.get("action") or "").strip()
    detail = str(request.args.get("detail") or "").strip()
    client_ip = str(request.args.get("clientIp") or "").strip()
    module = str(request.args.get("module") or "").strip()
    outcome = str(request.args.get("outcome") or "").strip().casefold()
    request_id = str(request.args.get("requestId") or "").strip()
    if timestamp:
        clauses.append("Timestamp LIKE ?")
        params.append(f"%{timestamp}%")
    if action:
        clauses.append("(Action LIKE ? OR ActionCode LIKE ?)")
        params.extend([f"%{action}%", f"%{action}%"])
    if detail:
        clauses.append("(Detail LIKE ? OR Summary LIKE ?)")
        params.extend([f"%{detail}%", f"%{detail}%"])
    if client_ip:
        clauses.append("ClientIP LIKE ?")
        params.append(f"%{client_ip}%")
    if module:
        clauses.append("Module = ?")
        params.append(module)
    if outcome in ("failure", "exception"):
        if outcome == "failure":
            clauses.append("Outcome IN ('failure', 'exception')")
        else:
            clauses.append("Outcome = ?")
            params.append(outcome)
    elif outcome:
        clauses.append("Outcome = ?")
        params.append(outcome)
    if request_id:
        clauses.append("RequestId LIKE ?")
        params.append(f"%{request_id}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def activity_log_row(row):
    keys = row.keys()
    summary = row["Summary"] if "Summary" in keys and row["Summary"] else row["Detail"]
    return {
        "id": row["ID"],
        "timestamp": row["Timestamp"],
        "action": row["Action"],
        "actionCode": row["ActionCode"] if "ActionCode" in keys else "",
        "detail": summary,
        "summary": summary,
        "clientIp": row["ClientIP"],
        "eventId": row["EventId"] if "EventId" in keys else "",
        "requestId": row["RequestId"] if "RequestId" in keys else "",
        "module": row["Module"] if "Module" in keys else "",
        "outcome": row["Outcome"] if "Outcome" in keys else "",
        "severity": row["Severity"] if "Severity" in keys else "",
        "resourceType": row["ResourceType"] if "ResourceType" in keys else "",
        "resourceId": row["ResourceId"] if "ResourceId" in keys else "",
        "userAgent": row["UserAgent"] if "UserAgent" in keys else "",
    }


LOG_SELECT = """
    ID, Timestamp, Action, Detail, ClientIP,
    EventId, RequestId, Module, ActionCode, Outcome, Severity,
    ResourceType, ResourceId, Summary, UserAgent
"""


@bp.get("/api/activity-logs")
def list_activity_logs():
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("pageSize", 80, type=int), 1), 500)
    where, params = activity_log_filters()
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM ActivityLogs {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT {LOG_SELECT}
            FROM ActivityLogs
            {where}
            ORDER BY ID DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
    return jsonify({
        "success": True,
        "data": [activity_log_row(row) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
    })


@bp.get("/api/activity-logs/export")
def export_activity_logs():
    where, params = activity_log_filters()
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT {LOG_SELECT}
            FROM ActivityLogs
            {where}
            ORDER BY ID DESC
            LIMIT 20000
            """,
            params,
        ).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Timestamp",
        "Module",
        "Action",
        "ActionCode",
        "Outcome",
        "Severity",
        "Detail",
        "ResourceType",
        "ResourceId",
        "ClientIP",
        "RequestId",
        "EventId",
    ])
    for row in rows:
        item = activity_log_row(row)
        writer.writerow([
            item["timestamp"],
            item["module"],
            item["action"],
            item["actionCode"],
            item["outcome"],
            item["severity"],
            item["detail"],
            item["resourceType"],
            item["resourceId"],
            item["clientIp"],
            item["requestId"],
            item["eventId"],
        ])
    csv_text = output.getvalue()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=activity-log-{stamp}.csv",
        },
    )


@bp.post("/api/activity-logs")
def create_activity_log():
    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip() or "UI event"
    detail = str(data.get("detail") or "").strip()
    if not is_key_log_action(action):
        return jsonify({"success": True, "skipped": True})
    stamp = log_event(action, detail)
    return jsonify({"success": True, "timestamp": stamp})
