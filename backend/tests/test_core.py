import os
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_PATH"] = str(TMP / "test.db")
os.environ["UPLOAD_DIR"] = str(TMP / "uploads")
os.environ["LOG_PATH"] = str(TMP / "test.log")
sys.path.insert(0, str(ROOT))

from flask import Flask
from werkzeug.exceptions import NotFound

from db import get_connection, migrate
from services.dashboard_analytics import format_minutes, minutes_between, parse_dashboard_record
from services.files_store import stored_path
from util import letters_only


def test_letters_only():
    assert letters_only("Maersk-Line 123") == "maerskline"
    assert letters_only("") == ""


def test_format_minutes():
    assert format_minutes(None) == ""
    assert format_minutes(17) == "17 min"
    assert format_minutes(120) == "2h"
    assert format_minutes(235) == "3h 55m"


def test_parse_dashboard_record():
    record, error = parse_dashboard_record({
        "orderNumber": "OD1",
        "date": "2026-08-21",
        "emailReceived": "2026-08-21 08:00:00",
        "handlingTime": "2026-08-21 08:10:00",
        "bookingConvertedTime": "2026-08-21 08:40:00",
    })
    assert error is None
    assert record["reportDate"] == "2026-08-21"
    assert record["processMinutes"] == 30
    assert minutes_between(
        __import__("datetime").datetime(2026, 8, 21, 8, 0, 0),
        __import__("datetime").datetime(2026, 8, 21, 8, 10, 0),
    ) == 10


def test_migrate_schema_version_once():
    migrate()
    with get_connection() as conn:
        version = conn.execute("SELECT Version FROM SchemaVersion WHERE ID=1").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM CustomerRemarks").fetchone()[0]
    assert version == 2
    assert count == 3
    migrate()
    with get_connection() as conn:
        count_again = conn.execute("SELECT COUNT(*) FROM CustomerRemarks").fetchone()[0]
    assert count_again == 3


def test_stored_path_rejects_traversal():
    migrate()
    flask_app = Flask(__name__)
    with flask_app.app_context():
        try:
            stored_path("../secret.txt")
            raised = False
        except NotFound:
            raised = True
    assert raised


def test_api_health_leave_dashboard():
    from app import app

    client = app.test_client()
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json()["success"] is True
    leave = client.get("/api/leave-plans?year=2026&month=8")
    assert leave.status_code == 200
    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    assert "kpis" in dashboard.get_json()["data"]


def test_audit_writes_sqlite_and_json():
    migrate()
    from config import LOG_PATH
    from logging_util import audit

    audit("record.create", summary="CQN / Demo Customer A", resource_id="1")
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ActivityLogs ORDER BY ID DESC LIMIT 1").fetchone()
    assert row["ActionCode"] == "record.create"
    assert row["Outcome"] == "success"
    assert row["Module"] == "records"
    assert "T" in row["Timestamp"] and row["Timestamp"].endswith("Z")
    lines = Path(LOG_PATH).read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert payload["event"] == "record.create"
    assert payload["outcome"] == "success"
    assert payload["level"] == "INFO"


def test_activity_log_failure_filter():
    migrate()
    from logging_util import audit
    from app import app

    audit("record.create", "failure", summary="duplicate key")
    audit("record.create", summary="ok row")
    client = app.test_client()
    data = client.get("/api/activity-logs?outcome=failure").get_json()["data"]
    assert data
    assert all(item["outcome"] in ("failure", "exception") for item in data)
    assert any(item["detail"] == "duplicate key" for item in data)


def test_get_list_does_not_audit():
    migrate()
    from app import app

    with get_connection() as conn:
        before = conn.execute("SELECT COUNT(*) FROM ActivityLogs").fetchone()[0]
    client = app.test_client()
    response = client.get("/api/customer-remarks")
    assert response.status_code == 200
    with get_connection() as conn:
        after = conn.execute("SELECT COUNT(*) FROM ActivityLogs").fetchone()[0]
    assert after == before


def test_unhandled_api_exception_is_audited():
    migrate()
    from app import create_app

    test_app = create_app()

    def boom():
        raise RuntimeError("boom-test")

    test_app.add_url_rule("/api/__test-boom", endpoint="test_boom_exc", view_func=boom)
    client = test_app.test_client()
    response = client.get("/api/__test-boom")
    assert response.status_code == 500
    body = response.get_json()
    assert body["success"] is False
    assert response.headers.get("X-Request-ID")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ActivityLogs WHERE ActionCode='server.exception' ORDER BY ID DESC LIMIT 1"
        ).fetchone()
    assert row is not None
    assert row["Outcome"] == "exception"
    assert "boom-test" in row["Summary"]


if __name__ == "__main__":
    names = [name for name, value in list(globals().items()) if name.startswith("test_") and callable(value)]
    failed = 0
    for name in names:
        try:
            globals()[name]()
            print(f"PASS {name}")
        except Exception as error:
            failed += 1
            print(f"FAIL {name}: {error}")
    raise SystemExit(failed)
