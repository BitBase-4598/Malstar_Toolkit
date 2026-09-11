import json
import re
import socket
import threading
import urllib.error
import urllib.request

import mammoth
from openpyxl import load_workbook

from config import (
    ASK_MAX_QUESTION,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_CHAT_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_TIMEOUT,
    PREVIEW_COLS,
    PREVIEW_ROWS,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_EXCERPT,
    RAG_TOP_K,
    llm_enabled,
)
from db import fts_ready, get_connection
from db_engine import OperationalError
from logging_util import audit
from services.files_store import cell_to_text, preview_docx, stored_path
from services.sops import load_sop
from util import now_stamp

SOURCE_LABELS = {
    "wiki": "Wiki",
    "sop": "SOP",
    "file": "File",
    "remark": "Remark",
    "case": "Case",
    "gca": "GCA",
    "icb": "ICB",
    "unloco": "UNLOCODE",
}
CATALOG_HINTS = {
    "unloco",
    "unlocode",
    "locode",
    "port",
    "harbour",
    "harbor",
    "icb",
    "agent",
    "station",
    "country",
    "branch",
    "controlling",
}
UNLOCO_CODE_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{3}\b")

_INDEX_LOCK = threading.Lock()
_INDEXING = False


def fts_available(conn):
    return fts_ready(conn, "RagChunksFts", "RagChunks")


def touch_index_state(conn):
    count = conn.execute("SELECT COUNT(*) FROM RagChunks").fetchone()[0]
    conn.execute(
        """
        INSERT INTO RagIndexState (ID, LastIndexedAt, ChunkCount)
        VALUES (1, ?, ?)
        ON CONFLICT(ID) DO UPDATE SET
            LastIndexedAt=excluded.LastIndexedAt,
            ChunkCount=excluded.ChunkCount
        """,
        (now_stamp(), count),
    )


def chunk_text(text, size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]
    pieces = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + size, length)
        if end < length:
            space = cleaned.rfind(" ", start + size // 2, end)
            if space > start:
                end = space
        piece = cleaned[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return pieces


def replace_source_chunks(conn, source_type, source_id, chunks, touch=True):
    conn.execute(
        "DELETE FROM RagChunks WHERE SourceType=? AND SourceID=?",
        (source_type, source_id),
    )
    stamp = now_stamp()
    for chunk in chunks:
        body = str(chunk.get("body") or "").strip()
        if not body:
            continue
        conn.execute(
            """
            INSERT INTO RagChunks (SourceType, SourceID, Title, Locator, Body, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_type,
                source_id,
                str(chunk.get("title") or "")[:300],
                str(chunk.get("locator") or "")[:120],
                body[:8000],
                stamp,
            ),
        )
    if touch:
        touch_index_state(conn)


def extract_docx_text(path):
    with path.open("rb") as handle:
        raw = mammoth.extract_raw_text(handle).value or ""
    text = re.sub(r"\s+", " ", raw).strip()
    if text:
        return text
    html = preview_docx(path).get("html") or ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def extract_xlsx_chunks(path, title, file_id):
    workbook = load_workbook(path, read_only=True, data_only=True)
    chunks = []
    try:
        for worksheet in workbook.worksheets:
            for row_index, row in enumerate(
                worksheet.iter_rows(max_col=PREVIEW_COLS, values_only=True), start=1
            ):
                if row_index > PREVIEW_ROWS:
                    break
                values = [cell_to_text(cell).strip() for cell in row]
                values = [item for item in values if item]
                if not values:
                    continue
                body = f"{title} | {worksheet.title} row {row_index}: " + " | ".join(values)
                chunks.append({
                    "title": title,
                    "locator": f"{worksheet.title} row {row_index}",
                    "body": body,
                    "sourceId": file_id,
                })
    finally:
        workbook.close()
    return chunks


def index_sop(conn, sop_id, touch=True):
    data = load_sop(conn, sop_id)
    if not data:
        replace_source_chunks(conn, "sop", sop_id, [], touch=touch)
        return
    title = data["title"]
    chunks = []
    header = [f"SOP: {title}", f"Status: {data['status']}"]
    if data.get("owner"):
        header.append(f"Owner: {data['owner']}")
    if data.get("revision"):
        header.append(f"Revision: {data['revision']}")
    if data.get("purpose"):
        header.append(f"Purpose: {data['purpose']}")
    chunks.append({
        "title": title,
        "locator": "overview",
        "body": "\n".join(header),
    })
    for step in data.get("steps") or []:
        instruction = str(step.get("instruction") or "").strip()
        if not instruction:
            continue
        number = step.get("stepNumber")
        chunks.append({
            "title": title,
            "locator": f"step {number}",
            "body": f"SOP {title} step {number}: {instruction}",
        })
    replace_source_chunks(conn, "sop", sop_id, chunks, touch=touch)


def index_file(conn, file_id, touch=True):
    row = conn.execute("SELECT * FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
    if not row:
        replace_source_chunks(conn, "file", file_id, [], touch=touch)
        return
    title = row["OriginalName"]
    path = stored_path(row["StoredName"])
    if not path.is_file():
        replace_source_chunks(conn, "file", file_id, [], touch=touch)
        return
    chunks = []
    try:
        if row["Kind"] == "image":
            chunks = []
        elif row["Kind"] == "docx":
            text = extract_docx_text(path)
            for index, piece in enumerate(chunk_text(text), start=1):
                chunks.append({
                    "title": title,
                    "locator": f"section {index}",
                    "body": f"{title}: {piece}",
                })
        elif row["Kind"] == "xlsx":
            chunks = extract_xlsx_chunks(path, title, file_id)
        else:
            chunks = []
    except Exception as error:
        audit(
            "file.index",
            "failure",
            resource_id=file_id,
            summary=f"{title}: {error}",
        )
        chunks = []
    replace_source_chunks(conn, "file", file_id, chunks, touch=touch)


def index_wiki(conn, page_id, touch=True):
    row = conn.execute("SELECT * FROM WikiPages WHERE ID=?", (page_id,)).fetchone()
    if not row:
        replace_source_chunks(conn, "wiki", page_id, [], touch=touch)
        return
    from services.wiki import markdown_sections

    title = row["Title"] or row["Path"]
    chunks = []
    header = [f"Wiki: {title}", f"Path: {row['Path']}"]
    if row["Folder"]:
        header.append(f"Folder: {row['Folder']}")
    chunks.append({
        "title": title,
        "locator": "overview",
        "body": "\n".join(header),
    })
    for heading, section in markdown_sections(row["Body"] or ""):
        for index, piece in enumerate(chunk_text(section), start=1):
            locator = heading if index == 1 else f"{heading} {index}"
            chunks.append({
                "title": title,
                "locator": locator[:120],
                "body": f"{title} ({locator}): {piece}",
            })
    replace_source_chunks(conn, "wiki", page_id, chunks, touch=touch)


def index_remark(conn, remark_id, touch=True):
    row = conn.execute("SELECT * FROM CustomerRemarks WHERE ID=?", (remark_id,)).fetchone()
    if not row:
        replace_source_chunks(conn, "remark", remark_id, [], touch=touch)
        return
    title = f"{row['CTRLOrgcode']} / {row['Customer']}"
    parts = [f"Customer remark {title}"]
    for label, key in (("Remark1", "Remark1"), ("Remark2", "Remark2"), ("Remark3", "Remark3")):
        value = str(row[key] or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    replace_source_chunks(
        conn,
        "remark",
        remark_id,
        [{"title": title, "locator": "record", "body": "\n".join(parts)}],
        touch=touch,
    )


def index_case(conn, case_id, touch=True):
    row = conn.execute("SELECT * FROM Cases WHERE ID=?", (case_id,)).fetchone()
    if not row:
        replace_source_chunks(conn, "case", case_id, [], touch=touch)
        return
    title = row["HBL"] or row["Name"] or f"Case {case_id}"
    parts = [
        f"Feedback case {title}",
        f"Status: {row['Status']}",
        f"Category: {row['Category']}",
    ]
    for label, key in (
        ("Description", "Description"),
        ("Wrongly identified", "WronglyIdentified"),
        ("Incorrect", "Incorrect"),
        ("Corrected", "Corrected"),
        ("Cause", "CauseOfError"),
        ("Action", "Action"),
    ):
        value = str(row[key] or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    replace_source_chunks(
        conn,
        "case",
        case_id,
        [{"title": title, "locator": row["Category"] or "case", "body": "\n".join(parts)}],
        touch=touch,
    )


def index_gca_feedback(conn, feedback_id, touch=True):
    row = conn.execute("SELECT * FROM GcaFeedback WHERE ID=?", (feedback_id,)).fetchone()
    if not row:
        replace_source_chunks(conn, "gca", feedback_id, [], touch=touch)
        return
    title = row["Hbl"] or row["HblKey"] or f"GCA {feedback_id}"
    parts = [
        f"GCA feedback {title}",
        f"Category: {row['Category']}",
        f"Lane: {row['Lane']}",
    ]
    for label, key in (
        ("Wrongly identified", "WronglyIdentified"),
        ("Incorrect", "Incorrect"),
        ("Corrected", "Corrected"),
        ("Cause", "Cause"),
        ("Description", "Description"),
        ("Action", "Action"),
    ):
        value = str(row[key] or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    replace_source_chunks(
        conn,
        "gca",
        feedback_id,
        [{"title": title, "locator": row["Category"] or "feedback", "body": "\n".join(parts)}],
        touch=touch,
    )


def reindex_all(conn):
    conn.execute("DELETE FROM RagChunks")
    for row in conn.execute("SELECT ID FROM Sops").fetchall():
        index_sop(conn, row["ID"], touch=False)
    for row in conn.execute("SELECT ID FROM ToolkitFiles").fetchall():
        index_file(conn, row["ID"], touch=False)
    for row in conn.execute("SELECT ID FROM WikiPages").fetchall():
        index_wiki(conn, row["ID"], touch=False)
    for row in conn.execute("SELECT ID FROM CustomerRemarks").fetchall():
        index_remark(conn, row["ID"], touch=False)
    for row in conn.execute("SELECT ID FROM Cases").fetchall():
        index_case(conn, row["ID"], touch=False)
    for row in conn.execute("SELECT ID FROM GcaFeedback").fetchall():
        index_gca_feedback(conn, row["ID"], touch=False)
    touch_index_state(conn)


def is_indexing():
    return _INDEXING


def _run_reindex():
    global _INDEXING
    try:
        with get_connection() as conn:
            reindex_all(conn)
    finally:
        _INDEXING = False


def start_backfill_if_needed(conn):
    global _INDEXING
    count = conn.execute("SELECT COUNT(*) FROM RagChunks").fetchone()[0]
    if count:
        return False
    files = conn.execute("SELECT COUNT(*) FROM ToolkitFiles").fetchone()[0]
    sops = conn.execute("SELECT COUNT(*) FROM Sops").fetchone()[0]
    wiki = conn.execute("SELECT COUNT(*) FROM WikiPages").fetchone()[0]
    remarks = conn.execute("SELECT COUNT(*) FROM CustomerRemarks").fetchone()[0]
    cases = conn.execute("SELECT COUNT(*) FROM Cases").fetchone()[0]
    gca = conn.execute("SELECT COUNT(*) FROM GcaFeedback").fetchone()[0]
    if not (files or sops or wiki or remarks or cases or gca):
        return False
    with _INDEX_LOCK:
        if _INDEXING:
            return True
        _INDEXING = True
    threading.Thread(target=_run_reindex, daemon=True).start()
    return True


def maybe_backfill_index(conn):
    return start_backfill_if_needed(conn)


def _source_count(conn, source_type):
    return conn.execute(
        "SELECT COUNT(DISTINCT SourceID) FROM RagChunks WHERE SourceType=?",
        (source_type,),
    ).fetchone()[0]


def rag_status(conn):
    indexing = start_backfill_if_needed(conn)
    state = conn.execute("SELECT LastIndexedAt, ChunkCount FROM RagIndexState WHERE ID=1").fetchone()
    icb_count = conn.execute("SELECT COUNT(*) FROM IcbStations").fetchone()[0]
    unloco_count = conn.execute("SELECT COUNT(*) FROM Unlocodes").fetchone()[0]
    chunk_count = state["ChunkCount"] if state else 0
    return {
        "chunkCount": chunk_count,
        "lastIndexedAt": state["LastIndexedAt"] if state else "",
        "llmEnabled": llm_enabled(),
        "indexing": bool(indexing or _INDEXING),
        "sources": {
            "sops": _source_count(conn, "sop"),
            "files": _source_count(conn, "file"),
            "wiki": _source_count(conn, "wiki"),
            "remarks": _source_count(conn, "remark"),
            "cases": _source_count(conn, "case"),
            "gca": _source_count(conn, "gca"),
            "icb": icb_count,
            "unloco": unloco_count,
        },
    }


def build_fts_query(question):
    terms = re.findall(r"[A-Za-z0-9]{2,}", question or "")
    if terms:
        return " OR ".join(terms[:24])
    stripped = re.sub(r"[^\w\s]", " ", question or "", flags=re.UNICODE).strip()
    if stripped:
        return '"' + stripped.replace('"', "") + '"'
    return None


def search_chunks(conn, question, limit=RAG_TOP_K):
    query = build_fts_query(question)
    rows = []
    if query and fts_available(conn):
        try:
            tsquery = " | ".join(f"{term}:*" for term in re.findall(r"[A-Za-z0-9]{2,}", query)[:24]) or query
            rows = conn.execute(
                """
                SELECT ID, SourceType, SourceID, Title, Locator, Body
                FROM RagChunks
                WHERE SearchTsv @@ to_tsquery('simple', ?)
                ORDER BY ts_rank(SearchTsv, to_tsquery('simple', ?)) DESC, ID DESC
                LIMIT ?
                """,
                (tsquery, tsquery, limit),
            ).fetchall()
        except OperationalError:
            rows = []
    if rows:
        return rows
    tokens = re.findall(r"[A-Za-z0-9]{2,}", question or "")
    if not tokens:
        leftover = (question or "").strip()
        tokens = [leftover] if leftover else []
    if not tokens:
        return []
    clauses = []
    params = []
    for token in tokens[:6]:
        like = f"%{token}%"
        clauses.append("(Title LIKE ? OR Locator LIKE ? OR Body LIKE ?)")
        params.extend([like, like, like])
    return conn.execute(
        f"""
        SELECT ID, SourceType, SourceID, Title, Locator, Body
        FROM RagChunks
        WHERE {' OR '.join(clauses)}
        ORDER BY ID DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()


def should_search_catalog(question):
    text = str(question or "")
    if UNLOCO_CODE_RE.search(text):
        return True
    tokens = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", text)}
    return bool(tokens & CATALOG_HINTS)


def _clip_excerpt(body):
    text = str(body or "").strip()
    if len(text) <= RAG_EXCERPT:
        return text
    clipped = text[: RAG_EXCERPT - 1]
    space = clipped.rfind(" ")
    return (clipped[:space] if space > 80 else clipped) + "…"


def chunk_to_citation(row):
    source_type = row["SourceType"]
    return {
        "sourceType": source_type,
        "sourceId": row["SourceID"],
        "title": row["Title"],
        "locator": row["Locator"],
        "excerpt": _clip_excerpt(row["Body"]),
        "label": SOURCE_LABELS.get(source_type, source_type),
    }


def icb_to_citation(item):
    title = " ".join(
        part for part in (item.get("country"), item.get("icbCode") or item.get("branch")) if part
    ).strip() or "ICB station"
    excerpt = " · ".join(
        str(part) for part in (
            item.get("location"),
            item.get("unloco"),
            item.get("agentCode"),
            item.get("notes"),
        ) if part
    )
    return {
        "sourceType": "icb",
        "sourceId": item.get("id"),
        "title": title,
        "locator": item.get("icbCode") or item.get("branch") or "station",
        "excerpt": _clip_excerpt(excerpt or title),
        "label": "ICB",
        "record": item,
    }


def unloco_to_citation(item):
    title = " ".join(
        part for part in (item.get("unCode"), item.get("portName")) if part
    ).strip() or "UNLOCODE"
    excerpt = " · ".join(
        str(part) for part in (
            item.get("countryName"),
            item.get("countryCode"),
            item.get("category"),
        ) if part
    )
    return {
        "sourceType": "unloco",
        "sourceId": item.get("id"),
        "title": title,
        "locator": item.get("unCode") or "location",
        "excerpt": _clip_excerpt(excerpt or title),
        "label": "UNLOCODE",
        "record": item,
    }


def catalog_citations(question, limit=3):
    if not should_search_catalog(question):
        return []
    from services.icb import list_icb_stations
    from services.unloco import list_unlocodes

    citations = []
    icb = list_icb_stations(question, page=1, page_size=limit)
    for item in icb.get("data") or []:
        citations.append(icb_to_citation(item))
    unloco = list_unlocodes(question, page=1, page_size=limit)
    for item in unloco.get("data") or []:
        citations.append(unloco_to_citation(item))
    return citations


def retrieve_citations(conn, question, limit=RAG_TOP_K):
    rows = search_chunks(conn, question, limit=limit)
    citations = [chunk_to_citation(row) for row in rows]
    extra = catalog_citations(question)
    seen = {(item["sourceType"], item["sourceId"]) for item in citations}
    for item in extra:
        key = (item["sourceType"], item["sourceId"])
        if key in seen:
            continue
        citations.append(item)
        seen.add(key)
        if len(citations) >= limit + 4:
            break
    return citations


def retrieve_only_answer(citations):
    if not citations:
        return (
            "No matching wiki notes, SOP, file, or toolkit excerpts were found. "
            "Try different words, edit a note, upload a file, or rebuild the index."
        )
    lines = [
        "Azure OpenAI is not configured, so here are the closest matches from the wiki and toolkit."
    ]
    for index, item in enumerate(citations, start=1):
        label = item.get("label") or item["sourceType"]
        lines.append(f"[{index}] {item['title']} ({label} · {item['locator']})")
        lines.append(item["excerpt"])
    return "\n".join(lines)


def generate_answer(question, citations):
    if not citations:
        return (
            "I could not find this in the indexed wiki notes, Files, SOPs, or toolkit tables. "
            "Try different words, or rebuild the index after uploading notes or files."
        ), None
    if not llm_enabled():
        return retrieve_only_answer(citations), None
    numbered = []
    for index, item in enumerate(citations, start=1):
        label = item.get("label") or item["sourceType"]
        numbered.append(
            f"[{index}] {label} \"{item['title']}\" ({item['locator']})\n{item['excerpt']}"
        )
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You answer questions using only the provided wiki notes, SOP, file, "
                    "customer remark, case, GCA, ICB, and UNLOCODE excerpts. "
                    "If the excerpts do not contain the answer, say you could not find it "
                    "in the indexed knowledge. Cite sources as [1], [2], and so on. "
                    "Do not invent procedures, file contents, or table values."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nSources:\n" + "\n\n".join(numbered),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }
    url = (
        f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_CHAT_DEPLOYMENT}"
        f"/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
    )
    request_obj = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=AZURE_OPENAI_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
        answer = (
            (data.get("choices") or [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if answer:
            return answer, None
        return retrieve_only_answer(citations), "Azure OpenAI returned an empty answer."
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        return retrieve_only_answer(citations), f"Azure OpenAI HTTP {error.code}: {detail}"
    except TimeoutError:
        return retrieve_only_answer(citations), "Azure OpenAI timed out."
    except socket.timeout:
        return retrieve_only_answer(citations), "Azure OpenAI timed out."
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            return retrieve_only_answer(citations), "Azure OpenAI timed out."
        return retrieve_only_answer(citations), str(error)
    except Exception as error:
        return retrieve_only_answer(citations), str(error)
