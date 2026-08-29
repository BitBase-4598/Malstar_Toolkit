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
    assert version == 4
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
    lcl_filters = client.get("/api/lcl/filters")
    assert lcl_filters.status_code == 200
    assert "years" in lcl_filters.get_json()["data"]


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


def test_activity_log_action_filter_returns_200():
    migrate()
    from logging_util import audit
    from app import app

    audit("record.create", summary="CQN / Demo Customer A", resource_id="1")
    client = app.test_client()
    response = client.get("/api/activity-logs?action=record")
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert any("record" in str(item.get("action") or "").lower() or "record" in str(item.get("actionCode") or "").lower() for item in body["data"])


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


def test_cases_crud_and_status():
    migrate()
    from app import app

    client = app.test_client()
    missing = client.post("/api/cases", json={"name": "Only name"})
    assert missing.status_code == 400
    created = client.post("/api/cases", json={
        "name": "Shenzhen review",
        "hbl": "HBL123",
        "category": "Wrong rate",
    })
    assert created.status_code == 201
    body = created.get_json()["data"]
    assert body["status"] == "pending_review"
    assert body["name"] == "Shenzhen review"
    case_id = body["id"]
    listed = client.get("/api/cases?q=HBL123").get_json()["data"]
    assert any(item["id"] == case_id for item in listed)
    patched = client.patch(f"/api/cases/{case_id}/status", json={"status": "closed"})
    assert patched.status_code == 200
    assert patched.get_json()["data"]["status"] == "closed"
    deleted = client.delete(f"/api/cases/{case_id}")
    assert deleted.status_code == 200
    missing_get = client.get(f"/api/cases/{case_id}")
    assert missing_get.status_code == 404


def test_case_file_upload_png_xlsx():
    from io import BytesIO

    from openpyxl import Workbook

    migrate()
    from app import app

    client = app.test_client()
    created = client.post("/api/cases", json={"name": "Attach demo", "hbl": "HBL-FILE"}).get_json()["data"]
    case_id = created["id"]
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    image = client.post(
        f"/api/cases/{case_id}/files",
        data={"file": (BytesIO(png), "screenshot.png")},
        content_type="multipart/form-data",
    )
    assert image.status_code == 201
    assert image.get_json()["data"]["kind"] == "image"
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "HBL"
    sheet["B1"] = "HBL-FILE"
    buffer = BytesIO()
    workbook.save(buffer)
    excel = client.post(
        f"/api/cases/{case_id}/files",
        data={"file": (BytesIO(buffer.getvalue()), "correction.xlsx")},
        content_type="multipart/form-data",
    )
    assert excel.status_code == 201
    assert excel.get_json()["data"]["kind"] == "xlsx"
    detail = client.get(f"/api/cases/{case_id}").get_json()["data"]
    assert detail["fileCount"] == 2
    with get_connection() as conn:
        library = conn.execute("SELECT COUNT(*) FROM ToolkitFiles").fetchone()[0]
    assert library == 0


def test_case_import_and_locked_update():
    from io import BytesIO

    migrate()
    from app import app

    client = app.test_client()
    csv_bytes = (
        "Name,HBL#,Email,Start time,Category,Description\n"
        "COSCO,HBL1,a@b.com,2026-08-01 09:00,Wrong rate,Needs check\n"
        ",MISSINGHBL,skip@x.com,2026-08-01 09:00,Wrong rate,\n"
    ).encode("utf-8")
    first = client.post(
        "/api/cases/import",
        data={"file": (BytesIO(csv_bytes), "cases.csv")},
        content_type="multipart/form-data",
    )
    assert first.status_code == 200
    body = first.get_json()
    assert body["imported"] == 1
    assert body["skipped"] == 1
    listed = client.get("/api/cases?q=HBL1").get_json()["data"]
    assert listed[0]["email"] == "a@b.com"
    case_id = listed[0]["id"]
    second = client.post(
        "/api/cases/import",
        data={"file": (BytesIO(csv_bytes), "cases.csv")},
        content_type="multipart/form-data",
    )
    assert second.get_json()["imported"] == 0
    assert second.get_json()["skipped"] >= 1
    updated = client.put(f"/api/cases/{case_id}", json={
        "status": "reviewed",
        "category": "Surcharge",
        "description": "Checked",
        "name": "HACKED",
        "email": "evil@x.com",
        "hbl": "NOPE",
    })
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["name"] == "COSCO"
    assert data["email"] == "a@b.com"
    assert data["hbl"] == "HBL1"
    assert data["status"] == "reviewed"
    assert data["category"] == "Surcharge"
    assert data["description"] == "Checked"
    rejected = client.put(f"/api/cases/{case_id}", json={"category": "Not a real category"})
    assert rejected.status_code == 400


def test_case_import_xlsx():
    from io import BytesIO

    from openpyxl import Workbook

    migrate()
    from app import app

    client = app.test_client()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Name", "HBL#", "Start time", "Category"])
    sheet.append(["ONE", "HBLX", "2026-08-02 10:00", "Free time"])
    buffer = BytesIO()
    workbook.save(buffer)
    result = client.post(
        "/api/cases/import",
        data={"file": (BytesIO(buffer.getvalue()), "cases.xlsx")},
        content_type="multipart/form-data",
    )
    assert result.status_code == 200
    assert result.get_json()["imported"] == 1
    row = client.get("/api/cases?q=HBLX").get_json()["data"][0]
    assert row["name"] == "ONE"
    assert row["category"] == "Free time"


def test_lcl_dimension_and_summary():
    from services.lcl import build_map, build_summary, parse_dimension
    from db import get_connection

    pieces, length, width, height = parse_dimension(" 2 x 120 x 80 x 60")
    assert pieces == 2
    assert length == 120
    migrate()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO LclShipments (
                ShipmentID, Direction, Year, MonthName, JobBranch, DestCtry, CountryName,
                Customer, IsBosch, Weight, Volume, DimensionRaw, Pieces, DimL, DimW, DimH, Chargeable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("S1", "Export", "2026", "May", "SIN", "DE", "Germany", "BOSCH", 1, 100, 0.5, "1 x 0 x 0 x 0", 1, 0, 0, 0, 0.5),
        )
        conn.execute(
            """
            INSERT INTO LclShipments (
                ShipmentID, Direction, Year, MonthName, JobBranch, DestCtry, CountryName,
                Customer, IsBosch, Weight, Volume, DimensionRaw, Pieces, DimL, DimW, DimH, Chargeable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("S2", "Export", "2026", "May", "SIN", "NL", "Netherlands", "PUMA", 0, 200, 1.5, "2 x 0 x 0 x 0", 2, 0, 0, 0, 1.5),
        )
    data = build_summary({"year": "2026"})
    assert data["kpis"]["shipments"] == 2
    assert data["kpis"]["avgVolume"] == 1.0
    assert data["byYearMonth"]["years"]
    assert data["byYearMonth"]["years"]
    mapped = build_map({"year": "2026"})
    points = mapped["points"] if isinstance(mapped, dict) else mapped
    codes = {item["iso2"] for item in points}
    assert "DE" in codes
    assert "NL" in codes
    assert mapped["arrows"]


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
