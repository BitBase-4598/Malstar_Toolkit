import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("DATABASE_PATH"):
    TMP = Path(tempfile.mkdtemp())
    os.environ["MALSTAR_SKIP_DOTENV"] = "1"
    os.environ.pop("DATABASE_URL", None)
    os.environ["DATABASE_PATH"] = str(TMP / "malstar_test.db")
    os.environ["UPLOAD_DIR"] = str(TMP / "uploads")
    os.environ["LOG_PATH"] = str(TMP / "test.log")
    os.environ["GCA_XLSX_PATH"] = str(TMP / "missing-gca.xlsx")
    os.environ["LCL_XLSX_PATH"] = str(TMP / "missing-lcl.xlsx")
    os.environ["UNLOCODE_CSV_PATH"] = str(TMP / "missing-unlocode.csv")
    os.environ["DE_LCL_XLSX_PATH"] = str(TMP / "missing-delcl.xlsx")
    os.environ["BOSCH_DE_XLSX_PATH"] = str(TMP / "missing-bosch-de.xlsx")
sys.path.insert(0, str(ROOT))

import pytest
from openpyxl import Workbook

from db import get_connection, migrate


IDENTITY = [
    "Order Number",
    "Shipment Number",
    "Message Id",
    "Date",
    "Email Received",
    "Order Status",
    "Email Status",
    "Handled By",
    "Handling Time",
    "Booking Converted Time",
    "Subject",
    "Mailbox",
]
PAIR = ["cargoDetail_serviceType__old", "cargoDetail_serviceType__new"]

SAMPLE_CANDIDATES = [
    os.environ.get("NONMOD_SAMPLE_XLSX") or "",
    "/home/ubuntu/.cursor/projects/workspace/uploads/oneplatform-metabase-merged-2026-11-03_59b8.xlsx",
]


def _sample_path():
    for raw in SAMPLE_CANDIDATES:
        if raw and Path(raw).is_file():
            return Path(raw)
    return None


def _reset():
    migrate()
    with get_connection() as conn:
        conn.execute("DELETE FROM NonModRows")
        conn.execute("DELETE FROM NonModUploads")


def _client():
    _reset()
    from app import app

    return app.test_client()


def _workbook(rows, headers=None, first_sheet_only_note=False):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers or (IDENTITY + PAIR))
    for row in rows:
        sheet.append(row)
    if first_sheet_only_note:
        extra = workbook.create_sheet("Ignored")
        extra.append(["Order Number"])
        extra.append(["SHOULD-NOT-LOAD"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _row(order, mailbox, old, new, day="2026-11-03", message_id="M1"):
    return [
        order,
        "S1",
        message_id,
        day,
        f"{day} 08:00:00",
        "Shipment Converted",
        "AI-Booking: Converted",
        "ann@example.com",
        f"{day} 08:10:00",
        f"{day} 08:40:00",
        "Subject",
        mailbox,
        old,
        new,
    ]


def _post(client, payload, filename, report_date=None):
    form = {"file": (BytesIO(payload), filename)}
    if report_date is not None:
        form["reportDate"] = report_date
    return client.post("/api/non-mod/upload", data=form, content_type="multipart/form-data")


def test_nonmod_upload_kpis_and_reads():
    client = _client()
    payload = _workbook(
        [
            _row("OD1", "ops@example.com", "CFS_CFS", "CFS_DOOR", message_id=4.687371405927506e17),
            _row("OD2", "ops@example.com", "SAME", "SAME"),
            _row("OD3", "desk@example.com", "", ""),
            _row("OD4", "ops@example.com", "", "FILLED"),
        ],
        first_sheet_only_note=True,
    )
    uploaded = _post(client, payload, "oneplatform-metabase-merged-2026-11-03_59b8.xlsx")
    assert uploaded.status_code == 200
    body = uploaded.get_json()
    assert body["success"] is True
    data = body["data"]
    assert data["meta"]["reportDate"] == "2026-11-03"
    assert data["meta"]["filename"].endswith(".xlsx")
    assert data["selectedBookings"] == 4
    assert data["matchedBookings"] == 3
    assert data["unmatchedBookings"] == 1
    assert data["modifiedPct"] == 0.75
    assert data["nonModPct"] == 0.25
    assert data["byMailbox"] == [
        {"mailbox": "ops@example.com", "count": 3, "matched": 3},
        {"mailbox": "desk@example.com", "count": 1, "matched": 0},
    ]
    assert data["fieldRanking"] == [
        {"path": "cargoDetail_serviceType", "count": 2},
    ]
    latest = client.get("/api/non-mod/latest")
    assert latest.status_code == 200
    assert latest.get_json()["data"]["selectedBookings"] == 4
    assert latest.get_json()["data"]["meta"]["rowCount"] == 4
    ranking = client.get("/api/non-mod/field-ranking").get_json()["data"]
    assert ranking["reportDate"] == "2026-11-03"
    assert ranking["fieldRanking"] == data["fieldRanking"]
    page = client.get("/api/non-mod/rows?reportDate=2026-11-03&page=1&pageSize=2")
    assert page.status_code == 200
    page_body = page.get_json()
    assert page_body["pagination"] == {
        "page": 1,
        "pageSize": 2,
        "total": 4,
        "totalPages": 2,
    }
    first = page_body["data"][0]
    assert first["orderNumber"] == "OD1"
    assert first["reportDate"] == "2026-11-03"
    assert first["messageId"] == "468737140592750592"
    assert "e" not in first["messageId"].lower()
    assert first["matched"] is True
    assert first["changes"]["cargoDetail_serviceType"] == {"old": "CFS_CFS", "new": "CFS_DOOR"}
    second_page = client.get("/api/non-mod/rows?reportDate=2026-11-03&page=2&pageSize=2").get_json()
    assert [row["orderNumber"] for row in second_page["data"]] == ["OD3", "OD4"]
    assert second_page["data"][0]["matched"] is False
    equal_row = client.get("/api/non-mod/rows?reportDate=2026-11-03&page=1&pageSize=10").get_json()["data"][1]
    assert equal_row["orderNumber"] == "OD2"
    assert equal_row["matched"] is True
    assert equal_row["changes"]["cargoDetail_serviceType"] == {"old": "SAME", "new": "SAME"}


def test_nonmod_report_date_resolution_and_replace():
    client = _client()
    early = _workbook([_row("OLD", "ops@example.com", "A", "B", day="2026-11-01")])
    later = _workbook([
        _row("NEW", "ops@example.com", "", "", day="2026-11-03"),
        _row("NEW2", "ops@example.com", "A", "B", day="2026-11-03"),
    ])
    assert _post(client, early, "merge.xlsx").status_code == 200
    assert client.get("/api/non-mod/latest").get_json()["data"]["meta"]["reportDate"] == "2026-11-01"
    assert _post(client, later, "daily.xlsx").status_code == 200
    latest = client.get("/api/non-mod/latest").get_json()["data"]
    assert latest["meta"]["reportDate"] == "2026-11-03"
    assert latest["selectedBookings"] == 2
    kept = client.get("/api/non-mod/rows?reportDate=2026-11-01").get_json()
    assert kept["pagination"]["total"] == 1
    assert kept["data"][0]["orderNumber"] == "OLD"
    replaced = _workbook([_row("ONLY", "desk@example.com", "", "", day="2026-11-01")])
    again = _post(client, replaced, "ignored-2026-12-31.xlsx", report_date="2026-11-01")
    assert again.status_code == 200
    assert again.get_json()["data"]["meta"]["reportDate"] == "2026-11-01"
    assert again.get_json()["data"]["selectedBookings"] == 1
    latest_after = client.get("/api/non-mod/latest").get_json()["data"]
    assert latest_after["meta"]["reportDate"] == "2026-11-03"
    rows = client.get("/api/non-mod/rows?reportDate=2026-11-01").get_json()["data"]
    assert [row["orderNumber"] for row in rows] == ["ONLY"]
    named = _workbook([_row("FILE", "ops@example.com", "", "", day="2026-11-03")])
    named_upload = _post(client, named, "oneplatform-metabase-merged-2026-10-01.xlsx")
    assert named_upload.status_code == 200
    assert named_upload.get_json()["data"]["meta"]["reportDate"] == "2026-10-01"
    stored = client.get("/api/non-mod/rows?reportDate=2026-10-01").get_json()["data"][0]
    assert stored["reportDate"] == "2026-11-03"
    tie = _workbook([
        _row("T1", "ops@example.com", "", "", day="2026-11-01"),
        _row("T2", "ops@example.com", "", "", day="2026-11-04"),
    ])
    tie_upload = _post(client, tie, "no-date-in-name.xlsx")
    assert tie_upload.status_code == 200
    assert tie_upload.get_json()["data"]["meta"]["reportDate"] == "2026-11-04"


def test_nonmod_keeps_unknown_path_pairs_and_rejects_bad_headers():
    client = _client()
    headers = IDENTITY + [
        "custom_path__old",
        "custom_path__new",
        "cargoDetail_etd__old",
        "cargoDetail_etd__new",
    ]
    payload = _workbook(
        [[
            "OD1", "S1", "M1", "2026-11-03", "", "", "", "", "", "", "Subject", "ops@example.com",
            "before", "after", "", "",
        ]],
        headers=headers,
    )
    uploaded = _post(client, payload, "custom-2026-11-03.xlsx")
    assert uploaded.status_code == 200
    row = client.get("/api/non-mod/rows?reportDate=2026-11-03&pageSize=10").get_json()["data"][0]
    assert row["changes"]["custom_path"] == {"old": "before", "new": "after"}
    assert row["changes"]["cargoDetail_etd"] == {"old": "", "new": ""}
    assert set(row["changes"]) == {"custom_path", "cargoDetail_etd"}
    ranking = uploaded.get_json()["data"]["fieldRanking"]
    assert ranking == [{"path": "custom_path", "count": 1}]

    missing = _post(
        client,
        _workbook([["OD1"]], headers=["Order Number"]),
        "bad-2026-11-03.xlsx",
    )
    assert missing.status_code == 400
    assert "Order Status" in missing.get_json()["message"]
    assert "Mailbox" in missing.get_json()["message"]

    unpaired = _post(
        client,
        _workbook([], headers=IDENTITY + ["orphan__old"]),
        "orphan-2026-11-03.xlsx",
    )
    assert unpaired.status_code == 400
    assert "orphan__new" in unpaired.get_json()["message"]

    unknown = _post(
        client,
        _workbook([], headers=IDENTITY + PAIR + ["Notes"]),
        "notes-2026-11-03.xlsx",
    )
    assert unknown.status_code == 400
    assert "Notes" in unknown.get_json()["message"]
    assert client.get("/api/non-mod/rows?reportDate=2026-11-03").get_json()["pagination"]["total"] == 1


def test_nonmod_rejects_non_xlsx_and_leaves_dashboard_bookings():
    client = _client()
    with get_connection() as conn:
        before = conn.execute("SELECT COUNT(*) FROM DashboardBookings").fetchone()[0]
        conn.execute(
            "INSERT INTO DashboardBookings (OrderNumber, Mailbox) VALUES ('KEEP-ME', 'ops@example.com')"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(DashboardBookings)")}
    assert "ChangesJson" not in columns
    rejected = _post(client, b"not-an-xlsx", "daily.csv")
    assert rejected.status_code == 400
    assert "xlsx" in rejected.get_json()["message"].lower()
    bad_date = _post(client, _workbook([_row("OD1", "ops@example.com", "", "")]), "ok.xlsx", report_date="03-11-2026")
    assert bad_date.status_code == 400
    empty = client.get("/api/non-mod/latest").get_json()["data"]
    assert empty["meta"] is None
    assert empty["selectedBookings"] == 0
    assert client.get("/api/non-mod/rows").get_json()["pagination"]["total"] == 0
    assert client.get("/api/non-mod/field-ranking").get_json()["data"]["fieldRanking"] == []
    missing = client.get("/api/non-mod/rows?reportDate=2026-11-03")
    assert missing.status_code == 404
    assert client.get("/api/non-mod/field-ranking?reportDate=2026-11-03").status_code == 404
    assert client.get("/api/non-mod/rows?reportDate=11/03/2026").status_code == 400
    assert _post(client, b"PK\x03\x04not-really", "broken.xlsx").status_code == 400
    with get_connection() as conn:
        kept = conn.execute(
            "SELECT OrderNumber FROM DashboardBookings WHERE OrderNumber='KEEP-ME'"
        ).fetchone()
        after = conn.execute("SELECT COUNT(*) FROM DashboardBookings").fetchone()[0]
        conn.execute("DELETE FROM DashboardBookings WHERE OrderNumber='KEEP-ME'")
    assert kept["OrderNumber"] == "KEEP-ME"
    assert after == before + 1


def test_nonmod_sample_workbook_contract():
    path = _sample_path()
    if path is None:
        pytest.skip("sample Non-Mod workbook is not on disk")
    client = _client()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO DashboardBookings (OrderNumber) VALUES ('SAMPLE-KEEP')"
        )
    uploaded = _post(client, path.read_bytes(), path.name)
    assert uploaded.status_code == 200
    data = uploaded.get_json()["data"]
    assert data["meta"]["reportDate"] == "2026-11-03"
    assert data["meta"]["rowCount"] == 125
    assert data["selectedBookings"] == 125
    assert data["matchedBookings"] == 72
    assert data["unmatchedBookings"] == 53
    assert data["modifiedPct"] == 0.576
    assert data["nonModPct"] == 0.424
    assert data["byMailbox"] == [
        {"mailbox": "CUSLCL.SZH@LnS.maersk.com", "count": 58, "matched": 36},
        {"mailbox": "CUSLCLEUR.SZH@LnS.maersk.com", "count": 32, "matched": 20},
        {"mailbox": "TWNLCL-CUS@LnS.maersk.com", "count": 15, "matched": 9},
        {"mailbox": "HKGLCL@LnS.maersk.com", "count": 14, "matched": 3},
        {"mailbox": "CN.BOSCH.CFSPRSEXP@lns.maersk.com", "count": 6, "matched": 4},
    ]
    assert data["fieldRanking"][0] == {"path": "cargoDetail_serviceType", "count": 26}
    assert {"path": "consignee_orgaCode", "count": 25} in data["fieldRanking"]
    assert len(data["fieldRanking"]) == 24
    ranked = {item["path"] for item in data["fieldRanking"]}
    assert "cargoDetail_etd" not in ranked
    assert "cargoDetail_dgDetail_dgUnCode" not in ranked
    assert "cargoDetail_goodsDetail_containers" not in ranked
    latest = client.get("/api/non-mod/latest").get_json()["data"]
    assert latest["matchedBookings"] == 72
    assert latest["fieldRanking"][0]["path"] == "cargoDetail_serviceType"
    first = client.get("/api/non-mod/rows?reportDate=2026-11-03&page=1&pageSize=1").get_json()["data"][0]
    assert first["orderNumber"] == "ODSP2611001063"
    assert first["shipmentNumber"] == "S26SHK10045799"
    assert first["orderStatus"] == "Shipment Converted"
    assert first["emailStatus"] == "AI-Booking: Converted"
    assert first["mailbox"] == "CN.BOSCH.CFSPRSEXP@lns.maersk.com"
    assert first["messageId"].isdigit()
    assert first["matched"] is True
    assert first["changes"]["cargoDetail_serviceType"] == {"old": "CFS_CFS", "new": "CFS_DOOR"}
    assert first["changes"]["cargoDetail_etd"] == {"old": "", "new": ""}
    assert len(first["changes"]) == 27
    full = client.get("/api/non-mod/rows?reportDate=2026-11-03&pageSize=200").get_json()
    assert full["pagination"]["total"] == 125
    assert len(full["data"]) == 125
    assert sum(1 for row in full["data"] if row["matched"]) == 72
    with get_connection() as conn:
        kept = conn.execute(
            "SELECT COUNT(*) FROM DashboardBookings WHERE OrderNumber='SAMPLE-KEEP'"
        ).fetchone()[0]
        conn.execute("DELETE FROM DashboardBookings WHERE OrderNumber='SAMPLE-KEEP'")
    assert kept == 1
