from datetime import datetime

from flask import Blueprint, jsonify, request

from config import DASHBOARD_MAX_ROWS
from db import get_connection
from logging_util import audit
from services.dashboard_analytics import (
    DASHBOARD_FIELDS,
    build_dashboard_payload,
    parse_dashboard_record,
)
from util import now_stamp

bp = Blueprint("dashboard", __name__)


def parse_dashboard_date_arg(name):
    value = str(request.args.get(name) or "").strip()
    if not value:
        return "", None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None, f"{name} must be YYYY-MM-DD."
    return value, None


@bp.get("/api/dashboard")
def get_dashboard():
    date_from, error = parse_dashboard_date_arg("dateFrom")
    if error:
        return jsonify({"success": False, "message": error}), 400
    date_to, error = parse_dashboard_date_arg("dateTo")
    if error:
        return jsonify({"success": False, "message": error}), 400
    with get_connection() as conn:
        data = build_dashboard_payload(conn, date_from, date_to)
    return jsonify({"success": True, "data": data})


@bp.post("/api/dashboard/import")
def import_dashboard():
    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("filename") or "daily-report.csv").strip() or "daily-report.csv"
    raw_rows = payload.get("records")
    if not isinstance(raw_rows, list):
        audit("dashboard.import", "failure", summary="JSON records missing")
        return jsonify({"success": False, "message": "No records were sent."}), 400
    if len(raw_rows) > DASHBOARD_MAX_ROWS:
        message = f"CSV is limited to {DASHBOARD_MAX_ROWS} rows."
        audit("dashboard.import", "failure", summary=message)
        return jsonify({"success": False, "message": message}), 400
    records = []
    errors = []
    for index, raw in enumerate(raw_rows, start=2):
        record, error = parse_dashboard_record(raw)
        if error:
            errors.append({"row": index, "message": error})
            continue
        if not any(record.get(key) for key, _label in DASHBOARD_FIELDS):
            continue
        records.append(record)
    if errors:
        audit(
            "dashboard.import",
            "failure",
            summary=f"file={filename} validation errors={len(errors)}",
        )
        return jsonify({
            "success": False,
            "message": "CSV validation failed. Nothing was imported.",
            "errors": errors[:100],
        }), 400
    if not records:
        audit("dashboard.import", "failure", summary=f"file={filename} no data rows")
        return jsonify({"success": False, "message": "CSV contains no data rows."}), 400
    stamp = now_stamp()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM DashboardBookings")
        conn.executemany(
            """
            INSERT INTO DashboardBookings (
                OrderNumber, ShipmentNumber, MessageId, ReportDate, EmailReceived,
                EmailStatus, HandledBy, HandlingTime, BookingConvertedTime,
                Subject, Mailbox, HandleWaitMinutes, ProcessMinutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["orderNumber"],
                    item["shipmentNumber"],
                    item["messageId"],
                    item["reportDate"],
                    item["emailReceived"],
                    item["emailStatus"],
                    item["handledBy"],
                    item["handlingTime"],
                    item["bookingConvertedTime"],
                    item["subject"],
                    item["mailbox"],
                    item["handleWaitMinutes"],
                    item["processMinutes"],
                )
                for item in records
            ],
        )
        conn.execute(
            """
            INSERT INTO DashboardMeta (ID, Filename, UploadedAt, RowCount)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(ID) DO UPDATE SET
                Filename=excluded.Filename,
                UploadedAt=excluded.UploadedAt,
                RowCount=excluded.RowCount
            """,
            (filename[:200], stamp, len(records)),
        )
        data = build_dashboard_payload(conn, "", "")
    audit("dashboard.import", summary=f"file={filename} rows={len(records)}")
    return jsonify({
        "success": True,
        "message": "Dashboard updated",
        "processed": len(records),
        "data": data,
    })
