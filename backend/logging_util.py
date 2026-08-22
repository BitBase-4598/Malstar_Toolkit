import json
import logging
import sqlite3
import sys
import traceback
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import g, has_request_context, request

from config import LOG_PATH
from db import get_connection

NOISY_LOG_ACTIONS = {
    "opened malstar_toolkit",
    "opened add form",
    "opened edit form",
    "opened section",
    "copied cell",
    "copy failed",
    "delete cancelled",
    "csv import started",
    "search",
    "list records",
    "ui event",
    "malstar_toolkit started",
    "file preview failed",
}

ACTION_CATALOG = {
    "record.create": {"module": "records", "label": "Record created", "resource_type": "customer_remark"},
    "record.update": {"module": "records", "label": "Record updated", "resource_type": "customer_remark"},
    "record.delete": {"module": "records", "label": "Record deleted", "resource_type": "customer_remark"},
    "record.import": {"module": "records", "label": "CSV import completed", "resource_type": "customer_remark"},
    "file.upload": {"module": "files", "label": "File uploaded", "resource_type": "file"},
    "file.rename": {"module": "files", "label": "File renamed", "resource_type": "file"},
    "file.delete": {"module": "files", "label": "File deleted", "resource_type": "file"},
    "file.index": {"module": "files", "label": "File index failed", "resource_type": "file"},
    "sop.create": {"module": "sops", "label": "SOP created", "resource_type": "sop"},
    "sop.update": {"module": "sops", "label": "SOP updated", "resource_type": "sop"},
    "sop.delete": {"module": "sops", "label": "SOP deleted", "resource_type": "sop"},
    "leave.create": {"module": "leave", "label": "Leave plan created", "resource_type": "leave_plan"},
    "leave.update": {"module": "leave", "label": "Leave plan updated", "resource_type": "leave_plan"},
    "leave.delete": {"module": "leave", "label": "Leave plan deleted", "resource_type": "leave_plan"},
    "dashboard.import": {"module": "dashboard", "label": "Dashboard imported", "resource_type": "dashboard"},
    "ask.query": {"module": "ask", "label": "Ask", "resource_type": "ask"},
    "ask.reindex": {"module": "ask", "label": "Ask index rebuilt", "resource_type": "ask"},
    "server.exception": {"module": "server", "label": "Unhandled exception", "resource_type": "server"},
}

LEGACY_ACTION_MAP = {
    "create failed": ("record.create", "failure"),
    "record created": ("record.create", "success"),
    "update failed": ("record.update", "failure"),
    "record updated": ("record.update", "success"),
    "delete failed": ("record.delete", "failure"),
    "record deleted": ("record.delete", "success"),
    "csv import failed": ("record.import", "failure"),
    "csv import completed": ("record.import", "success"),
    "file upload failed": ("file.upload", "failure"),
    "file uploaded": ("file.upload", "success"),
    "file renamed": ("file.rename", "success"),
    "file deleted": ("file.delete", "success"),
    "sop create failed": ("sop.create", "failure"),
    "sop created": ("sop.create", "success"),
    "sop update failed": ("sop.update", "failure"),
    "sop updated": ("sop.update", "success"),
    "sop deleted": ("sop.delete", "success"),
    "leave plan create failed": ("leave.create", "failure"),
    "leave plan created": ("leave.create", "success"),
    "leave plan update failed": ("leave.update", "failure"),
    "leave plan updated": ("leave.update", "success"),
    "leave plan deleted": ("leave.delete", "success"),
    "dashboard import failed": ("dashboard.import", "failure"),
    "dashboard imported": ("dashboard.import", "success"),
    "ask": ("ask.query", "success"),
    "ask index rebuilt": ("ask.reindex", "success"),
}

FAILURE_LABELS = {
    "record.create": "Record create failed",
    "record.update": "Record update failed",
    "record.delete": "Record delete failed",
    "record.import": "CSV import failed",
    "file.upload": "File upload failed",
    "file.rename": "File rename failed",
    "file.delete": "File delete failed",
    "file.index": "File index failed",
    "sop.create": "SOP create failed",
    "sop.update": "SOP update failed",
    "sop.delete": "SOP delete failed",
    "leave.create": "Leave plan create failed",
    "leave.update": "Leave plan update failed",
    "leave.delete": "Leave plan delete failed",
    "dashboard.import": "Dashboard import failed",
    "ask.query": "Ask failed",
    "ask.reindex": "Ask reindex failed",
    "server.exception": "Unhandled exception",
}


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": utc_now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "audit", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if value is not None and value != "":
                    payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)[:4000]
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_file_logger():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("malstar")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


APP_LOGGER = setup_file_logger()


def current_request_id():
    if has_request_context():
        return str(getattr(g, "request_id", "") or "")
    return ""


def assign_request_id():
    incoming = ""
    if has_request_context():
        incoming = str(request.headers.get("X-Request-ID") or "").strip()[:80]
    request_id = incoming or str(uuid.uuid4())
    if has_request_context():
        g.request_id = request_id
    return request_id


def current_client_ip():
    if not has_request_context():
        return ""
    return str(request.remote_addr or "")[:80]


def current_user_agent():
    if not has_request_context():
        return ""
    return str(request.headers.get("User-Agent") or "")[:240]


def is_key_log_action(action):
    name = str(action or "").strip().casefold()
    if not name or name in NOISY_LOG_ACTIONS:
        return False
    if name.startswith(("get ", "opened ", "copied ", "post /", "put /", "patch /", "delete /")):
        return False
    return True


def _action_label(action, outcome):
    if outcome in ("failure", "exception"):
        return FAILURE_LABELS.get(action) or ACTION_CATALOG.get(action, {}).get("label") or action
    return ACTION_CATALOG.get(action, {}).get("label") or action


def _severity(outcome):
    if outcome == "exception":
        return "error"
    if outcome == "failure":
        return "warning"
    return "info"


def _safe_extra(extra):
    if not extra:
        return None
    cleaned = {}
    for key, value in extra.items():
        name = str(key).casefold()
        if any(token in name for token in ("password", "secret", "token", "api_key", "apikey", "authorization")):
            continue
        text = str(value)
        cleaned[str(key)] = text[:500]
    return cleaned or None


def audit(
    action,
    outcome="success",
    *,
    module="",
    resource_type="",
    resource_id="",
    summary="",
    extra=None,
    exc_info=None,
):
    catalog = ACTION_CATALOG.get(action, {})
    module = module or catalog.get("module") or "server"
    resource_type = resource_type or catalog.get("resource_type") or ""
    outcome = str(outcome or "success").strip().casefold()
    if outcome not in ("success", "failure", "exception"):
        outcome = "success"
    severity = _severity(outcome)
    label = _action_label(action, outcome)
    event_id = str(uuid.uuid4())
    request_id = current_request_id()
    stamp = utc_now_iso()
    summary = str(summary or "").strip()[:2000]
    resource_id = str(resource_id or "")[:80]
    client_ip = current_client_ip()
    user_agent = current_user_agent()
    extra_data = _safe_extra(extra)
    if exc_info is True:
        exc_info = sys.exc_info()
    if exc_info and exc_info[0] is None:
        exc_info = None

    payload = {
        "event_id": event_id,
        "request_id": request_id,
        "event": action,
        "outcome": outcome,
        "severity": severity,
        "module": module,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "summary": summary,
        "actor_ip": client_ip,
        "user_agent": user_agent,
    }
    if extra_data:
        payload["extra"] = extra_data
    if outcome == "exception" and exc_info:
        payload["exc"] = "".join(traceback.format_exception(*exc_info))[:4000]

    log_method = APP_LOGGER.error if severity == "error" else (
        APP_LOGGER.warning if severity == "warning" else APP_LOGGER.info
    )
    log_method(label, extra={"audit": payload}, exc_info=exc_info if outcome == "exception" else None)

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ActivityLogs (
                    Timestamp, Action, Detail, ClientIP,
                    EventId, RequestId, Module, ActionCode, Outcome, Severity,
                    ResourceType, ResourceId, Summary, UserAgent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stamp,
                    label[:200],
                    summary[:2000],
                    client_ip,
                    event_id,
                    request_id[:80],
                    module[:40],
                    action[:80],
                    outcome[:20],
                    severity[:20],
                    resource_type[:40],
                    resource_id,
                    summary[:2000],
                    user_agent,
                ),
            )
    except sqlite3.Error as error:
        APP_LOGGER.error(
            "audit persist failed",
            extra={"audit": {"event": "server.exception", "outcome": "exception", "summary": str(error)[:500]}},
        )
    return stamp


def log_event(action, detail=""):
    if not is_key_log_action(action):
        return utc_now_iso()
    mapped = LEGACY_ACTION_MAP.get(str(action or "").strip().casefold())
    if mapped:
        code, outcome = mapped
        return audit(code, outcome, summary=detail)
    outcome = "failure" if "fail" in str(action or "").casefold() else "success"
    return audit(str(action).strip()[:80], outcome, summary=detail)
