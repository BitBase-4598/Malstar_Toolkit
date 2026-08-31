import csv
import re
from io import StringIO

from db import get_connection
from util import now_stamp

HEADER_MAP = {
    "country": "country",
    "location": "location",
    "cw1 branch": "branch",
    "branch": "branch",
    "cw1 unloco code consol": "unloco",
    "cw1 unloco code": "unloco",
    "unloco": "unloco",
    "cw1 group code": "groupCode",
    "group code": "groupCode",
    "cw1 group name": "groupName",
    "group name": "groupName",
    "cw1 agent code": "agentCode",
    "agent code": "agentCode",
    "icb code": "icbCode",
    "icb": "icbCode",
    "notes": "notes",
}

NA_VALUES = {"", "-", "—", "–", "n/a", "na", "none", "null", "tbc"}


def normalize_header(value):
    text = str(value or "").strip().lower()
    text = text.replace("(consol)", "consol")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def clean_text(value):
    text = str(value or "").replace("\u00a0", " ").replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def flatten_unloco(value):
    text = clean_text(value)
    parts = []
    for chunk in re.split(r"[\n,;/]+", text):
        token = " ".join(chunk.split())
        if token and token.casefold() not in NA_VALUES:
            parts.append(token)
    return ", ".join(parts)


def direction_from_group(group_code, group_name):
    code = clean_text(group_code).upper()
    name = clean_text(group_name).casefold()
    if "-FIS" in code or code.endswith("FIS") or "import" in name:
        return "import"
    if "-FES" in code or code.endswith("FES") or "-GES" in code or "export" in name or "gateway" in name:
        return "export"
    return ""


def split_code_and_notes(value):
    text = " ".join(clean_text(value).split())
    if not text:
        return "", ""
    match = re.match(r"^([A-Za-z0-9._-]+)(?:\s+(.*))?$", text)
    if not match:
        return text, ""
    code = match.group(1)
    rest = (match.group(2) or "").strip()
    return code, rest


def row_to_dict(row):
    return {
        "id": row["ID"],
        "country": row["Country"],
        "location": row["Location"],
        "branch": row["Branch"],
        "unloco": row["Unloco"],
        "groupCode": row["GroupCode"],
        "groupName": row["GroupName"],
        "agentCode": row["AgentCode"],
        "icbCode": row["IcbCode"],
        "notes": row["Notes"],
        "direction": row["Direction"],
    }


def decode_csv(data):
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_icb_csv(data):
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
    if "country" not in mapping and "branch" not in mapping and "icbCode" not in mapping:
        return [], "CSV must include Country, CW1 Branch, or ICB Code."
    records = []
    for raw in reader:
        if not raw or not any(clean_text(cell) for cell in raw):
            continue
        def col(name):
            index = mapping.get(name)
            if index is None or index >= len(raw):
                return ""
            return raw[index]

        country = " ".join(clean_text(col("country")).split())
        location = " ".join(clean_text(col("location")).split())
        branch = " ".join(clean_text(col("branch")).split())
        group_code = " ".join(clean_text(col("groupCode")).split())
        group_name = " ".join(clean_text(col("groupName")).split())
        unloco = flatten_unloco(col("unloco"))
        agent_raw = clean_text(col("agentCode"))
        icb_raw = clean_text(col("icbCode"))
        extra_notes = " ".join(clean_text(col("notes")).split())
        agent_code, agent_notes = split_code_and_notes(agent_raw)
        icb_code, icb_notes = split_code_and_notes(icb_raw)
        if not icb_code and icb_raw:
            icb_code = " ".join(icb_raw.split())
        notes_parts = [part for part in (extra_notes, icb_notes, agent_notes) if part]
        notes = " | ".join(dict.fromkeys(notes_parts))
        if not any((country, location, branch, unloco, agent_code, icb_code, group_code)):
            continue
        records.append({
            "country": country,
            "location": location,
            "branch": branch,
            "unloco": unloco,
            "groupCode": group_code,
            "groupName": group_name,
            "agentCode": agent_code or " ".join(agent_raw.split()),
            "icbCode": icb_code,
            "notes": notes,
            "direction": direction_from_group(group_code, group_name),
        })
    if not records:
        return [], "CSV contains no station rows."
    return records, None


def import_icb_csv(filename, data):
    records, error = parse_icb_csv(data)
    if error:
        return None, error
    stamp = now_stamp()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM IcbStations")
        conn.executemany(
            """
            INSERT INTO IcbStations (
                Country, Location, Branch, Unloco, GroupCode, GroupName,
                AgentCode, IcbCode, Notes, Direction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["country"],
                    item["location"],
                    item["branch"],
                    item["unloco"],
                    item["groupCode"],
                    item["groupName"],
                    item["agentCode"],
                    item["icbCode"],
                    item["notes"],
                    item["direction"],
                )
                for item in records
            ],
        )
        conn.execute(
            """
            INSERT INTO IcbImportMeta (ID, Filename, ImportedAt, RowCount)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(ID) DO UPDATE SET
                Filename=excluded.Filename,
                ImportedAt=excluded.ImportedAt,
                RowCount=excluded.RowCount
            """,
            ((filename or "icb.csv")[:200], stamp, len(records)),
        )
    return {"filename": (filename or "icb.csv")[:200], "rowCount": len(records), "importedAt": stamp}, None


def list_icb_stations(query="", page=1, page_size=100):
    q = clean_text(query)
    page = max(int(page or 1), 1)
    page_size = min(max(int(page_size or 100), 1), 500)
    where = ""
    params = []
    if q:
        like = f"%{q}%"
        where = """
            WHERE Country LIKE ? COLLATE NOCASE
               OR Location LIKE ? COLLATE NOCASE
               OR Branch LIKE ? COLLATE NOCASE
               OR Unloco LIKE ? COLLATE NOCASE
               OR GroupCode LIKE ? COLLATE NOCASE
               OR GroupName LIKE ? COLLATE NOCASE
               OR AgentCode LIKE ? COLLATE NOCASE
               OR IcbCode LIKE ? COLLATE NOCASE
               OR Notes LIKE ? COLLATE NOCASE
        """
        params = [like] * 9
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM IcbStations {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM IcbStations {where}
            ORDER BY Country COLLATE NOCASE, Location COLLATE NOCASE, Branch COLLATE NOCASE, ID
            LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        meta_row = None
        meta_row = conn.execute("SELECT * FROM IcbImportMeta WHERE ID=1").fetchone()
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
