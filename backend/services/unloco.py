import csv
import json
import re
import sqlite3
from io import StringIO
from pathlib import Path

from config import UNLOCODE_CSV_PATH
from db import get_connection, rebuild_unlocodes_fts
from util import fts_prefix_query, now_stamp

FLAG_DEFS = (
    ("oceanPrimary", "Ocean Primary", "is ocean primary code"),
    ("isActive", "Active", "rl isactive"),
    ("isSystem", "System", "rl issystem"),
    ("hasAirport", "Airport", "rl hasairport"),
    ("hasSeaport", "Seaport", "rl hasseaport"),
    ("hasRail", "Rail", "rl hasrail"),
    ("hasRoad", "Road", "rl hasroad"),
    ("hasPost", "Post", "rl haspost"),
    ("hasCustomsLodge", "Customs Lodge", "rl hascustomslodge"),
    ("hasUnload", "Unload", "rl hasunload"),
    ("hasStore", "Store", "rl hasstore"),
    ("hasTerminal", "Terminal", "rl hasterminal"),
    ("hasDischarge", "Discharge", "rl hasdischarge"),
    ("hasOutport", "Outport", "rl hasoutport"),
    ("hasBorderCrossing", "Border Crossing", "rl hasbordercrossing"),
)

HEADER_MAP = {
    "rl portname": "portName",
    "portname": "portName",
    "port name": "portName",
    "un code": "unCode",
    "uncode": "unCode",
    "unloco": "unCode",
    "rl rn nkcountrycode": "countryCode",
    "countrycode": "countryCode",
    "country code": "countryCode",
    "country name": "countryName",
    "countryname": "countryName",
    "lcl category": "category",
    "category": "category",
}
HEADER_MAP.update({header: key for key, _label, header in FLAG_DEFS})

TRUE_VALUES = {"true", "1", "yes", "y", "t"}


def normalize_header(value):
    text = str(value or "").strip().lower().replace("\ufeff", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def clean_text(value):
    text = str(value or "").replace("\u00a0", " ").replace("\ufeff", "")
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def parse_bool(value):
    return clean_text(value).casefold() in TRUE_VALUES


def decode_csv(data):
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def row_to_dict(row):
    flags = []
    try:
        stored = json.loads(row["Flags"] or "[]")
    except json.JSONDecodeError:
        stored = []
    if stored and isinstance(stored[0], dict) and "label" in stored[0]:
        by_id = {item.get("id"): item for item in stored if isinstance(item, dict)}
        flags = [
            {
                "id": key,
                "label": (by_id.get(key) or {}).get("label") or label,
                "on": bool((by_id.get(key) or {}).get("on")),
            }
            for key, label, _header in FLAG_DEFS
        ]
    else:
        on_labels = {item for item in stored if isinstance(item, str)}
        flags = [{"id": key, "label": label, "on": label in on_labels} for key, label, _header in FLAG_DEFS]
    return {
        "id": row["ID"],
        "portName": row["PortName"],
        "unCode": row["UnCode"],
        "countryCode": row["CountryCode"],
        "countryName": row["CountryName"],
        "category": row["Category"],
        "flags": flags,
    }


def parse_unloco_csv(data):
    text = decode_csv(data)
    if not text.strip():
        return [], "CSV is empty."
    reader = csv.reader(StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        return [], "CSV header row is missing."
    mapping = {}
    for index, cell in enumerate(raw_header):
        key = HEADER_MAP.get(normalize_header(cell))
        if key and key not in mapping:
            mapping[key] = index
    if "unCode" not in mapping and "portName" not in mapping:
        return [], "CSV must include UN Code or Port Name."
    records = []
    for raw in reader:
        if not raw or not any(clean_text(cell) for cell in raw):
            continue

        def col(name):
            index = mapping.get(name)
            if index is None or index >= len(raw):
                return ""
            return raw[index]

        port_name = clean_text(col("portName"))
        un_code = clean_text(col("unCode")).upper()
        country_code = clean_text(col("countryCode")).upper()
        country_name = clean_text(col("countryName"))
        category = clean_text(col("category"))
        if not un_code and not port_name:
            continue
        flags = [
            {"id": key, "label": label, "on": parse_bool(col(key))}
            for key, label, _header in FLAG_DEFS
        ]
        search_text = " ".join(part for part in (port_name, un_code, country_code, country_name) if part)
        records.append({
            "portName": port_name,
            "unCode": un_code,
            "countryCode": country_code,
            "countryName": country_name,
            "category": category,
            "flags": json.dumps(flags, separators=(",", ":")),
            "searchText": search_text,
        })
    if not records:
        return [], "CSV contains no UNLOCODE rows."
    return records, None


def import_unloco_csv(filename, data):
    records, error = parse_unloco_csv(data)
    if error:
        return None, error
    stamp = now_stamp()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM Unlocodes")
        conn.executemany(
            """
            INSERT INTO Unlocodes (
                PortName, UnCode, CountryCode, CountryName, Category, Flags, SearchText
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["portName"],
                    item["unCode"],
                    item["countryCode"],
                    item["countryName"],
                    item["category"],
                    item["flags"],
                    item["searchText"],
                )
                for item in records
            ],
        )
        conn.execute(
            """
            INSERT INTO UnlocoImportMeta (ID, Filename, ImportedAt, RowCount)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(ID) DO UPDATE SET
                Filename=excluded.Filename,
                ImportedAt=excluded.ImportedAt,
                RowCount=excluded.RowCount
            """,
            ((filename or "UNLOCODE.csv")[:200], stamp, len(records)),
        )
        rebuild_unlocodes_fts(conn)
        conn.execute("ANALYZE Unlocodes")
    return {"filename": (filename or "UNLOCODE.csv")[:200], "rowCount": len(records), "importedAt": stamp}, None


def ensure_unloco_loaded():
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM Unlocodes").fetchone()[0]
    if count:
        return None, None
    path = Path(UNLOCODE_CSV_PATH)
    if not path.is_file():
        return None, None
    return import_unloco_csv(path.name, path.read_bytes())


def fts_available(conn):
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='UnlocodesFts'"
        ).fetchone()
        return bool(row)
    except sqlite3.OperationalError:
        return False


UNLOCO_LIST_COLS = (
    "u.ID, u.PortName, u.UnCode, u.CountryCode, u.CountryName, u.Category, u.Flags"
)
UNLOCO_TABLE_COLS = (
    "ID, PortName, UnCode, CountryCode, CountryName, Category, Flags"
)
UNLOCO_LIST_ORDER = "CountryCode, PortName, UnCode, ID"


def list_unlocodes(query="", page=1, page_size=50):
    q = clean_text(query)
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 50), 1), 200)
    offset = (page - 1) * page_size
    with get_connection() as conn:
        meta_row = conn.execute("SELECT * FROM UnlocoImportMeta WHERE ID=1").fetchone()
        meta_total = int(meta_row["RowCount"]) if meta_row else 0
        rows = []
        total = 0
        if not q:
            total = meta_total or conn.execute("SELECT COUNT(*) FROM Unlocodes").fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT {UNLOCO_TABLE_COLS} FROM Unlocodes
                ORDER BY {UNLOCO_LIST_ORDER}
                LIMIT ? OFFSET ?
                """,
                (page_size, offset),
            ).fetchall()
        else:
            match = fts_prefix_query(q)
            used_fts = False
            if match and fts_available(conn):
                try:
                    total = conn.execute(
                        "SELECT COUNT(*) FROM UnlocodesFts WHERE UnlocodesFts MATCH ?",
                        (match,),
                    ).fetchone()[0]
                    rows = conn.execute(
                        f"""
                        SELECT {UNLOCO_LIST_COLS} FROM UnlocodesFts
                        JOIN Unlocodes u ON u.ID = UnlocodesFts.rowid
                        WHERE UnlocodesFts MATCH ?
                        ORDER BY rank, u.ID
                        LIMIT ? OFFSET ?
                        """,
                        (match, page_size, offset),
                    ).fetchall()
                    used_fts = True
                except sqlite3.OperationalError:
                    used_fts = False
            if not used_fts:
                like = f"%{q}%"
                where = "WHERE SearchText LIKE ? COLLATE NOCASE"
                params = [like]
                total = conn.execute(f"SELECT COUNT(*) FROM Unlocodes {where}", params).fetchone()[0]
                rows = conn.execute(
                    f"""
                    SELECT {UNLOCO_TABLE_COLS} FROM Unlocodes {where}
                    ORDER BY {UNLOCO_LIST_ORDER}
                    LIMIT ? OFFSET ?
                    """,
                    params + [page_size, offset],
                ).fetchall()
    meta = {
        "filename": meta_row["Filename"] if meta_row else "",
        "importedAt": meta_row["ImportedAt"] if meta_row else "",
        "rowCount": meta_row["RowCount"] if meta_row else total,
    }
    return {
        "data": [row_to_dict(row) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
        "meta": meta,
    }


def bump_unloco_row_count(conn, delta=1):
    conn.execute(
        """
        INSERT INTO UnlocoImportMeta (ID, Filename, ImportedAt, RowCount)
        VALUES (1, 'manual', '', ?)
        ON CONFLICT(ID) DO UPDATE SET RowCount=UnlocoImportMeta.RowCount + excluded.RowCount
        """,
        (max(int(delta), 0),),
    )


def create_unlocode(payload):
    port_name = clean_text((payload or {}).get("portName"))
    un_code = clean_text((payload or {}).get("unCode")).upper()
    country_code = clean_text((payload or {}).get("countryCode")).upper()
    country_name = clean_text((payload or {}).get("countryName"))
    category = clean_text((payload or {}).get("category"))
    if not un_code and not port_name:
        return None, "UNLOCODE or Port is required."
    flags = [
        {"id": key, "label": label, "on": False}
        for key, label, _header in FLAG_DEFS
    ]
    search_text = " ".join(part for part in (port_name, un_code, country_code, country_name) if part)
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO Unlocodes (
                PortName, UnCode, CountryCode, CountryName, Category, Flags, SearchText
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                port_name,
                un_code,
                country_code,
                country_name,
                category,
                json.dumps(flags, separators=(",", ":")),
                search_text,
            ),
        )
        bump_unloco_row_count(conn)
        row = conn.execute("SELECT * FROM Unlocodes WHERE ID=?", (cur.lastrowid,)).fetchone()
    return row_to_dict(row), None
