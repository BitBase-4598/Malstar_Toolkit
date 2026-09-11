#!/usr/bin/env python3
"""Archival one-shot: copy an old MALSTAR SQLite file into PostgreSQL.

The running app no longer opens SQLite. Use this only to load a leftover .db.

Usage (from the backend directory):

    python scripts/sqlite_to_postgres.py --sqlite customer_remark.db
    # DATABASE_URL comes from the environment or repo-root .env
    # or pass --database-url "postgresql://nathan:...@malstar.postgres.database.azure.com:5432/malstar?sslmode=require"
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import envfile  # noqa: E402,F401

SKIP_TABLES = {
    "sqlite_sequence",
    "sqlite_stat1",
    "sqlite_stat2",
    "sqlite_stat3",
    "sqlite_stat4",
    "ragchunksfts",
    "unlocodesfts",
    "icbstationsfts",
}
SKIP_COLUMNS = {"searchtsv"}
COPY_ORDER = (
    "SchemaVersion",
    "CustomerRemarks",
    "ActivityLogs",
    "ToolkitFiles",
    "Sops",
    "SopSteps",
    "SopAttachments",
    "LeavePeople",
    "LeavePlans",
    "DashboardMeta",
    "DashboardBookings",
    "RagChunks",
    "RagIndexState",
    "Cases",
    "CaseFiles",
    "LclShipments",
    "LclImportMeta",
    "IcbStations",
    "IcbImportMeta",
    "Unlocodes",
    "UnlocoImportMeta",
    "GcaBookings",
    "GcaFeedback",
    "GcaImportMeta",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Copy SQLite data into PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="Path to customer_remark.db")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="PostgreSQL DATABASE_URL (defaults to DATABASE_URL / .env)",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("pass --database-url or set DATABASE_URL in the environment / .env")
    return args


def sqlite_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [row[0] for row in rows]


def sqlite_columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def copy_table(sqlite_conn, pg_conn, table):
    columns = [name for name in sqlite_columns(sqlite_conn, table) if name.lower() not in SKIP_COLUMNS]
    if not columns:
        return 0
    rows = sqlite_conn.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    if not rows:
        return 0
    placeholders = ", ".join("?" for _ in columns)
    col_sql = ", ".join(columns)
    pg_conn.execute(f"DELETE FROM {table}")
    pg_conn.executemany(
        f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})",
        [tuple(row[name] for name in columns) for row in rows],
    )
    if any(name.lower() == "id" for name in columns):
        pg_conn.execute(
            f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                GREATEST(COALESCE((SELECT MAX(id) FROM {table}), 1), 1)
            )
            """
        )
    return len(rows)


def main():
    args = parse_args()
    sqlite_path = Path(args.sqlite).expanduser().resolve()
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    os.environ["DATABASE_URL"] = args.database_url
    from db import migrate
    from db_engine import connect

    migrate()
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    present = {name.lower(): name for name in sqlite_tables(sqlite_conn)}
    copied = {}
    with connect() as pg_conn:
        for table in COPY_ORDER:
            actual = present.get(table.lower())
            if not actual:
                continue
            copied[table] = copy_table(sqlite_conn, pg_conn, actual)
        for name in present.values():
            if name.lower() in SKIP_TABLES or name.lower().endswith("fts"):
                continue
            if name.lower() not in {item.lower() for item in copied}:
                copied[name] = copy_table(sqlite_conn, pg_conn, name)
    sqlite_conn.close()
    print("Copied tables:")
    for table, count in copied.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
