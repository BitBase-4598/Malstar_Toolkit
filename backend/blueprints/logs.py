import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from db import get_connection
from logging_util import is_key_log_action, log_event
from webutil import json_dict, query_int, respond

router = APIRouter()


def activity_log_filters(request: Request):
    clauses = []
    params = []
    timestamp = str(request.query_params.get("timestamp") or "").strip()
    action = str(request.query_params.get("action") or "").strip()
    detail = str(request.query_params.get("detail") or "").strip()
    client_ip = str(request.query_params.get("clientIp") or "").strip()
    module = str(request.query_params.get("module") or "").strip()
    outcome = str(request.query_params.get("outcome") or "").strip().casefold()
    request_id = str(request.query_params.get("requestId") or "").strip()
    if timestamp:
        clauses.append("LOWER(Timestamp) LIKE LOWER(?)")
        params.append(f"%{timestamp}%")
    if action:
        clauses.append("(LOWER(Action) LIKE LOWER(?) OR LOWER(ActionCode) LIKE LOWER(?))")
        params.extend([f"%{action}%", f"%{action}%"])
    if detail:
        clauses.append("(LOWER(Detail) LIKE LOWER(?) OR LOWER(Summary) LIKE LOWER(?))")
        params.extend([f"%{detail}%", f"%{detail}%"])
    if client_ip:
        clauses.append("LOWER(ClientIP) LIKE LOWER(?)")
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
        clauses.append("LOWER(RequestId) LIKE LOWER(?)")
        params.append(f"%{request_id}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def activity_log_row(row):
    summary = row["Summary"] or row["Detail"]
    return {
        "id": row["ID"],
        "timestamp": row["Timestamp"],
        "action": row["Action"],
        "actionCode": row["ActionCode"] or "",
        "detail": summary,
        "summary": summary,
        "clientIp": row["ClientIP"],
        "eventId": row["EventId"] or "",
        "requestId": row["RequestId"] or "",
        "module": row["Module"] or "",
        "outcome": row["Outcome"] or "",
        "severity": row["Severity"] or "",
        "resourceType": row["ResourceType"] or "",
        "resourceId": row["ResourceId"] or "",
        "userAgent": row["UserAgent"] or "",
    }


LOG_SELECT = """
    ID, Timestamp, Action, Detail, ClientIP,
    EventId, RequestId, Module, ActionCode, Outcome, Severity,
    ResourceType, ResourceId, Summary, UserAgent
"""


@router.get("/api/activity-logs")
def list_activity_logs(request: Request):
    page = max(query_int(request, "page", 1), 1)
    page_size = min(max(query_int(request, "pageSize", 80), 1), 500)
    where, params = activity_log_filters(request)
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
    return respond({
        "success": True,
        "data": [activity_log_row(row) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
    })


@router.get("/api/activity-logs/export")
def export_activity_logs(request: Request):
    where, params = activity_log_filters(request)
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
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=activity-log-{stamp}.csv"},
    )


@router.post("/api/activity-logs")
def create_activity_log(data: dict = Depends(json_dict)):
    action = str(data.get("action") or "").strip() or "UI event"
    detail = str(data.get("detail") or "").strip()
    if not is_key_log_action(action):
        return respond({"success": True, "skipped": True})
    stamp = log_event(action, detail)
    return respond({"success": True, "timestamp": stamp})
