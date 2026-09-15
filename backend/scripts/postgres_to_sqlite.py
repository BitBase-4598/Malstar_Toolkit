#!/usr/bin/env python3
"""Read-only copy of SearchBar + Leave Forecast tables from Azure Postgres into SQLite.

Copies only CustomerRemarks, LeavePeople, and LeavePlans. Other MALSTAR tables are
created empty by migrate(). This script never INSERT/UPDATE/DELETEs on Postgres.

Usage (from the backend directory):

    pip install "psycopg[binary]"
    python scripts/postgres_to_sqlite.py --sqlite malstar.db

Password comes from --password, PGPASSWORD, or MALSTAR_PG_PASSWORD. Do not commit it.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COPY_TABLES = ("CustomerRemarks", "LeavePeople", "LeavePlans")
FALLBACK_DBNAME = "malstar"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Copy CustomerRemarks and leave tables from Azure Postgres into SQLite"
    )
    parser.add_argument(
        "--sqlite",
        default=str(ROOT / "malstar.db"),
        help="Destination SQLite file (default: backend/malstar.db)",
    )
    parser.add_argument("--host", default="malstar.postgres.database.azure.com")
    parser.add_argument("--dbname", default="postgres")
    parser.add_argument("--user", default="nathan")
    parser.add_argument(
        "--password",
        default=os.environ.get("PGPASSWORD") or os.environ.get("MALSTAR_PG_PASSWORD", ""),
        help="Postgres password (or set PGPASSWORD / MALSTAR_PG_PASSWORD)",
    )
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--sslmode", default="require")
    parser.add_argument(
        "--no-fallback-db",
        action="store_true",
        help=f"Do not try database {FALLBACK_DBNAME} if copy tables are missing",
    )
    args = parser.parse_args()
    if not args.password:
        parser.error("pass --password or set PGPASSWORD / MALSTAR_PG_PASSWORD")
    return args


def connect_postgres(args, dbname):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        raise SystemExit("pip install 'psycopg[binary]' to run this copy script") from None

    conn = psycopg.connect(
        host=args.host,
        dbname=dbname,
        user=args.user,
        password=args.password,
        port=args.port,
        sslmode=args.sslmode,
        autocommit=True,
        connect_timeout=15,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    )
    return conn


def public_tables(pg_conn):
    rows = pg_conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    ).fetchall()
    return {str(row["table_name"]) for row in rows}


def resolve_table(names, wanted):
    lookup = {name.lower(): name for name in names}
    return lookup.get(wanted.lower())


def copy_tables_present(names):
    return all(resolve_table(names, table) for table in COPY_TABLES)


def cell(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat(timespec="seconds")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, bool):
        return int(value)
    return value


def sqlite_columns(sqlite_conn, table):
    return [row[1] for row in sqlite_conn.execute(f"PRAGMA table_info({table})")]


def copy_table(pg_conn, sqlite_conn, pg_table, sqlite_table):
    dest_cols = sqlite_columns(sqlite_conn, sqlite_table)
    dest_lookup = {name.lower(): name for name in dest_cols}
    pg_cols = [
        str(row["column_name"])
        for row in pg_conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (pg_table,),
        ).fetchall()
    ]
    paired = []
    for pg_name in pg_cols:
        sqlite_name = dest_lookup.get(pg_name.lower())
        if sqlite_name:
            paired.append((pg_name, sqlite_name))
    if not paired:
        return 0
    select_sql = ", ".join(f'"{pg_name}"' for pg_name, _sqlite_name in paired)
    rows = pg_conn.execute(f'SELECT {select_sql} FROM "{pg_table}"').fetchall()
    sqlite_conn.execute(f"DELETE FROM {sqlite_table}")
    if not rows:
        return 0
    sqlite_names = [sqlite_name for _pg_name, sqlite_name in paired]
    placeholders = ", ".join("?" for _ in sqlite_names)
    col_sql = ", ".join(sqlite_names)
    payload = []
    for row in rows:
        values = []
        for pg_name, _sqlite_name in paired:
            if pg_name in row:
                raw = row[pg_name]
            else:
                raw = row[pg_name.lower()] if pg_name.lower() in row else None
            values.append(cell(raw))
        payload.append(tuple(values))
    sqlite_conn.executemany(
        f"INSERT INTO {sqlite_table} ({col_sql}) VALUES ({placeholders})",
        payload,
    )
    return len(payload)


def reset_sqlite_sequence(sqlite_conn, table):
    row = sqlite_conn.execute(f"SELECT MAX(ID) FROM {table}").fetchone()
    max_id = row[0] if row and row[0] is not None else 0
    sqlite_conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
    if max_id:
        sqlite_conn.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)",
            (table, max_id),
        )


def open_source(args):
    tried = []
    dbnames = [args.dbname]
    if not args.no_fallback_db and FALLBACK_DBNAME.lower() != args.dbname.lower():
        dbnames.append(FALLBACK_DBNAME)
    last_error = None
    for dbname in dbnames:
        try:
            conn = connect_postgres(args, dbname)
        except Exception as exc:
            last_error = exc
            tried.append(f"{dbname}: connect failed ({exc})")
            continue
        names = public_tables(conn)
        if copy_tables_present(names):
            if tried:
                print(f"Database {dbname!r} has the copy tables; earlier: {'; '.join(tried)}")
            return conn, dbname, names
        conn.close()
        preview = ", ".join(sorted(names)[:20]) or "(none)"
        tried.append(f"{dbname}: missing copy tables; public tables: {preview}")
    detail = "; ".join(tried) if tried else str(last_error)
    raise SystemExit(
        "Could not find CustomerRemarks / LeavePeople / LeavePlans on Azure Postgres. "
        f"{detail}. If this is a firewall block, run the script from an allowed network."
    )


def main():
    args = parse_args()
    sqlite_path = Path(args.sqlite).expanduser().resolve()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ["MALSTAR_SKIP_DOTENV"] = "1"
    os.environ.pop("DATABASE_URL", None)
    os.environ["DATABASE_PATH"] = str(sqlite_path)

    pg_conn, dbname, names = open_source(args)
    print(f"Reading Postgres database {dbname!r} on {args.host} as {args.user} (read-only)")

    from db import migrate
    from db_engine import connect

    migrate()
    copied = {}
    with connect(sqlite_path) as sqlite_conn:
        for table in COPY_TABLES:
            pg_table = resolve_table(names, table)
            copied[table] = copy_table(pg_conn, sqlite_conn, pg_table, table)
            reset_sqlite_sequence(sqlite_conn, table)
    pg_conn.close()
    print(f"Wrote {sqlite_path}")
    for table, count in copied.items():
        print(f"  {table}: {count}")
    empty = [table for table, count in copied.items() if count == 0]
    if empty:
        print(f"Warning: empty tables: {', '.join(empty)}")


if __name__ == "__main__":
    main()
