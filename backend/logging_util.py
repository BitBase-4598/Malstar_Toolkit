import logging
import sqlite3
from logging.handlers import RotatingFileHandler

from flask import request

from config import LOG_PATH
from db import get_connection
from util import now_stamp

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


def setup_file_logger():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("malstar")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


APP_LOGGER = setup_file_logger()


def is_key_log_action(action):
    name = str(action or "").strip().casefold()
    if not name or name in NOISY_LOG_ACTIONS:
        return False
    if name.startswith(("get ", "opened ", "copied ", "post /", "put /", "patch /", "delete /")):
        return False
    return True


def log_event(action, detail=""):
    if not is_key_log_action(action):
        return now_stamp()
    stamp = now_stamp()
    try:
        client_ip = request.remote_addr or ""
    except RuntimeError:
        client_ip = ""
    detail = str(detail or "").strip()
    line = f"{stamp} | {action}"
    if detail:
        line += f" | {detail}"
    if client_ip:
        line += f" | ip={client_ip}"
    APP_LOGGER.info(line)
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ActivityLogs (Timestamp, Action, Detail, ClientIP)
                VALUES (?, ?, ?, ?)
                """,
                (stamp, action[:200], detail[:2000], client_ip[:80]),
            )
    except sqlite3.Error:
        pass
    return stamp
