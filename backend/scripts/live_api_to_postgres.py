#!/usr/bin/env python3
"""Copy live MALSTAR App Service API data into PostgreSQL.

Use this only when the SQLite file cannot be downloaded from Kudu.
Uploads and raw LCL shipment rows are not exposed by the public APIs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import envfile  # noqa: E402,F401
from util import letters_only  # noqa: E402

DEFAULT_APP = "https://malstar-toolkit-djexgna2eghtgkep.eastasia-01.azurewebsites.net"


def parse_args():
    parser = argparse.ArgumentParser(description="Copy live App Service API data into PostgreSQL")
    parser.add_argument("--app-url", default=os.environ.get("MALSTAR_APP_URL", DEFAULT_APP))
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="PostgreSQL DATABASE_URL (defaults to DATABASE_URL / .env)",
    )
    args = parser.parse_args()
    args.app_url = args.app_url.rstrip("/")
    if not args.database_url:
        parser.error("pass --database-url or set DATABASE_URL in the environment / .env")
    return args


def fetch_json(app_url, path, params=None, timeout=90):
    query = f"?{urlencode(params)}" if params else ""
    request = Request(f"{app_url}{path}{query}", headers={"User-Agent": "malstar-cutover/1"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def fetch_pages(app_url, path, page_size, extra=None):
    first = fetch_json(app_url, path, {**(extra or {}), "page": 1, "pageSize": page_size})
    rows = list(first.get("data") or [])
    pagination = first.get("pagination") or {}
    total_pages = int(pagination.get("totalPages") or 1)
    if total_pages <= 1:
        return rows, first

    def one(page):
        payload = fetch_json(app_url, path, {**(extra or {}), "page": page, "pageSize": page_size})
        return page, payload.get("data") or []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(one, page) for page in range(2, total_pages + 1)]
        by_page = {}
        for future in as_completed(futures):
            page, data = future.result()
            by_page[page] = data
    for page in range(2, total_pages + 1):
        rows.extend(by_page[page])
    return rows, first


def fetch_leave_plans(app_url):
    rows = []
    seen = set()
    for year in range(2024, 2028):
        for month in range(1, 13):
            payload = fetch_json(app_url, "/api/leave-plans", {"year": year, "month": month})
            for row in payload.get("data") or []:
                key = (row.get("id"), row.get("person"), row.get("leaveDate"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def reset_id(conn, table):
    conn.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), 1)
        )
        """
    )


def main():
    args = parse_args()
    os.environ["DATABASE_URL"] = args.database_url
    from db import migrate
    from db_engine import connect

    print(f"Fetching {args.app_url}")
    remarks, _ = fetch_pages(args.app_url, "/api/customer-remarks", 10000)
    print(f"  remarks {len(remarks)}")
    people = fetch_json(args.app_url, "/api/leave-people").get("data") or []
    print(f"  leave people {len(people)}")
    plans = fetch_leave_plans(args.app_url)
    print(f"  leave plans {len(plans)}")
    logs, _ = fetch_pages(args.app_url, "/api/activity-logs", 500)
    print(f"  logs {len(logs)}")
    icb, icb_first = fetch_pages(args.app_url, "/api/icb", 500)
    print(f"  icb {len(icb)}")
    unloco, unloco_first = fetch_pages(args.app_url, "/api/unlocode", 200)
    print(f"  unlocode {len(unloco)}")
    gca_bookings, _ = fetch_pages(args.app_url, "/api/gca/bookings", 200)
    print(f"  gca bookings {len(gca_bookings)}")
    gca_feedback, _ = fetch_pages(args.app_url, "/api/gca/feedback", 200)
    print(f"  gca feedback {len(gca_feedback)}")
    dashboard = fetch_json(args.app_url, "/api/dashboard", timeout=120).get("data") or {}
    dash_rows = dashboard.get("rows") or []
    dash_meta = dashboard.get("meta") or {}
    print(f"  dashboard {len(dash_rows)}")
    gca_meta = (fetch_json(args.app_url, "/api/gca/summary").get("data") or {}).get("meta") or {}

    migrate()
    with connect() as conn:
        conn.execute("DELETE FROM CustomerRemarks")
        conn.executemany(
            """
            INSERT INTO CustomerRemarks
                (ID, CTRLOrgcode, Customer, CustomerLetters, Remark1, Remark2, Remark3, CreateTime, UpdateTime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row.get("ctrlOrgcode") or "",
                    row.get("customer") or "",
                    letters_only(row.get("customer") or ""),
                    row.get("remark1") or "",
                    row.get("remark2") or "",
                    row.get("remark3") or "",
                    row.get("createTime") or "",
                    row.get("updateTime") or "",
                )
                for row in remarks
            ],
        )
        reset_id(conn, "CustomerRemarks")

        conn.execute("DELETE FROM LeavePeople")
        conn.executemany(
            "INSERT INTO LeavePeople (Email, Name) VALUES (?, ?)",
            [(row.get("email") or "", row.get("name") or "") for row in people if row.get("name")],
        )

        conn.execute("DELETE FROM LeavePlans")
        conn.executemany(
            """
            INSERT INTO LeavePlans (ID, LeaveDate, Person, LeaveType, Status, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("leaveDate") or "",
                    row.get("person") or "",
                    row.get("leaveType") or "annual",
                    row.get("status") or "planned",
                    row.get("createdAt") or "",
                    row.get("updatedAt") or "",
                )
                for row in plans
            ],
        )
        reset_id(conn, "LeavePlans")

        conn.execute("DELETE FROM ActivityLogs")
        conn.executemany(
            """
            INSERT INTO ActivityLogs (
                ID, Timestamp, Action, Detail, ClientIP, EventId, RequestId, Module,
                ActionCode, Outcome, Severity, ResourceType, ResourceId, Summary, UserAgent
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("timestamp") or "",
                    row.get("action") or "",
                    row.get("detail") or "",
                    row.get("clientIp") or "",
                    row.get("eventId") or "",
                    row.get("requestId") or "",
                    row.get("module") or "",
                    row.get("actionCode") or "",
                    row.get("outcome") or "",
                    row.get("severity") or "",
                    row.get("resourceType") or "",
                    row.get("resourceId") or "",
                    row.get("summary") or row.get("detail") or "",
                    row.get("userAgent") or "",
                )
                for row in logs
            ],
        )
        reset_id(conn, "ActivityLogs")

        conn.execute("DELETE FROM IcbStations")
        conn.executemany(
            """
            INSERT INTO IcbStations (
                ID, Country, Location, Branch, Unloco, GroupCode, GroupName,
                AgentCode, IcbCode, Notes, Direction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("country") or "",
                    row.get("location") or "",
                    row.get("branch") or "",
                    row.get("unloco") or "",
                    row.get("groupCode") or "",
                    row.get("groupName") or "",
                    row.get("agentCode") or "",
                    row.get("icbCode") or "",
                    row.get("notes") or "",
                    row.get("direction") or "",
                )
                for row in icb
            ],
        )
        reset_id(conn, "IcbStations")
        icb_meta = icb_first.get("meta") or {}
        conn.execute("DELETE FROM IcbImportMeta")
        conn.execute(
            """
            INSERT INTO IcbImportMeta (ID, Filename, ImportedAt, RowCount)
            VALUES (1, ?, ?, ?)
            """,
            (icb_meta.get("filename") or "", icb_meta.get("importedAt") or "", len(icb)),
        )

        conn.execute("DELETE FROM Unlocodes")
        conn.executemany(
            """
            INSERT INTO Unlocodes (
                ID, PortName, UnCode, CountryCode, CountryName, Category, Flags, SearchText
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("portName") or "",
                    row.get("unCode") or "",
                    row.get("countryCode") or "",
                    row.get("countryName") or "",
                    row.get("category") or "",
                    json.dumps(row.get("flags") or [], separators=(",", ":")),
                    " ".join(
                        part
                        for part in (
                            row.get("portName") or "",
                            row.get("unCode") or "",
                            row.get("countryCode") or "",
                            row.get("countryName") or "",
                        )
                        if part
                    ),
                )
                for row in unloco
            ],
        )
        reset_id(conn, "Unlocodes")
        unloco_meta = unloco_first.get("meta") or {}
        conn.execute("DELETE FROM UnlocoImportMeta")
        conn.execute(
            """
            INSERT INTO UnlocoImportMeta (ID, Filename, ImportedAt, RowCount)
            VALUES (1, ?, ?, ?)
            """,
            (unloco_meta.get("filename") or "", unloco_meta.get("importedAt") or "", len(unloco)),
        )

        conn.execute("DELETE FROM GcaFeedback")
        conn.execute("DELETE FROM GcaBookings")
        conn.executemany(
            """
            INSERT INTO GcaBookings (
                ID, BookingDate, SequenceNo, OrderId, BookingId, Name, Status, Remark,
                Uid, Scm, Hbl, HblKey, Lane, Branch, Category, IsAi
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("date") or "",
                    row.get("sequenceNo") or "",
                    row.get("orderId") or "",
                    row.get("bookingId") or "",
                    row.get("name") or "",
                    row.get("status") or "",
                    row.get("remark") or "",
                    row.get("uid") or "",
                    row.get("scm") or "",
                    row.get("hbl") or "",
                    row.get("hblKey") or "",
                    row.get("lane") or "",
                    row.get("branch") or "",
                    row.get("category") or "",
                    1 if row.get("isAi") else 0,
                )
                for row in gca_bookings
            ],
        )
        conn.executemany(
            """
            INSERT INTO GcaFeedback (
                ID, Hbl, HblKey, AdjustedHbl, WronglyIdentified, Incorrect, Corrected, Cause,
                GscPic, Category, Description, Action, FeedbackDate, Week, Email, Name, Lane
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("hbl") or "",
                    row.get("hblKey") or "",
                    row.get("adjustedHbl") or "",
                    row.get("wronglyIdentified") or "",
                    row.get("incorrect") or "",
                    row.get("corrected") or "",
                    row.get("cause") or "",
                    row.get("gscPic") or "",
                    row.get("category") or "",
                    row.get("description") or "",
                    row.get("action") or "",
                    row.get("date") or "",
                    row.get("week") or "",
                    row.get("email") or "",
                    row.get("name") or "",
                    row.get("lane") or "",
                )
                for row in gca_feedback
            ],
        )
        reset_id(conn, "GcaBookings")
        reset_id(conn, "GcaFeedback")
        conn.execute("DELETE FROM GcaImportMeta")
        conn.execute(
            """
            INSERT INTO GcaImportMeta (ID, Filename, ImportedAt, BookingCount, FeedbackCount)
            VALUES (1, ?, ?, ?, ?)
            """,
            (
                gca_meta.get("filename") or "",
                gca_meta.get("importedAt") or "",
                len(gca_bookings),
                len(gca_feedback),
            ),
        )

        conn.execute("DELETE FROM DashboardBookings")
        conn.executemany(
            """
            INSERT INTO DashboardBookings (
                ID, OrderNumber, ShipmentNumber, MessageId, ReportDate, EmailReceived,
                EmailStatus, HandledBy, HandlingTime, BookingConvertedTime, Subject,
                Mailbox, HandleWaitMinutes, ProcessMinutes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("id"),
                    row.get("orderNumber") or "",
                    row.get("shipmentNumber") or "",
                    row.get("messageId") or "",
                    row.get("date") or "",
                    row.get("emailReceived") or "",
                    row.get("emailStatus") or "",
                    row.get("handledBy") or "",
                    row.get("handlingTime") or "",
                    row.get("bookingConvertedTime") or "",
                    row.get("subject") or "",
                    row.get("mailbox") or "",
                    row.get("handleWaitMinutes"),
                    row.get("processMinutes"),
                )
                for row in dash_rows
            ],
        )
        reset_id(conn, "DashboardBookings")
        conn.execute("DELETE FROM DashboardMeta")
        conn.execute(
            """
            INSERT INTO DashboardMeta (ID, Filename, UploadedAt, RowCount)
            VALUES (1, ?, ?, ?)
            """,
            (
                dash_meta.get("filename") or "",
                dash_meta.get("uploadedAt") or "",
                len(dash_rows),
            ),
        )

    print("Copied from live API:")
    print(f"  CustomerRemarks: {len(remarks)}")
    print(f"  LeavePeople: {len(people)}")
    print(f"  LeavePlans: {len(plans)}")
    print(f"  ActivityLogs: {len(logs)}")
    print(f"  IcbStations: {len(icb)}")
    print(f"  Unlocodes: {len(unloco)}")
    print(f"  GcaBookings: {len(gca_bookings)}")
    print(f"  GcaFeedback: {len(gca_feedback)}")
    print(f"  DashboardBookings: {len(dash_rows)}")
    print("Skipped: ToolkitFiles binaries, LclShipments, Cases, SOPs (empty or not exposed).")


if __name__ == "__main__":
    main()
