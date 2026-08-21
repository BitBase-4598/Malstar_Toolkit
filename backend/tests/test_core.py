import os
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
    assert version == 1
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
