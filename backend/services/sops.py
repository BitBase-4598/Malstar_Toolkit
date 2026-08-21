from db import get_connection
from services.files_store import file_to_dict


def load_sop(conn, sop_id):
    row = conn.execute("SELECT * FROM Sops WHERE ID=?", (sop_id,)).fetchone()
    if not row:
        return None
    steps = conn.execute(
        """
        SELECT ID, StepNumber, Instruction
        FROM SopSteps WHERE SopID=? ORDER BY StepNumber, ID
        """,
        (sop_id,),
    ).fetchall()
    attachments = conn.execute(
        """
        SELECT f.* FROM ToolkitFiles f
        INNER JOIN SopAttachments a ON a.FileID = f.ID
        WHERE a.SopID=?
        ORDER BY f.OriginalName
        """,
        (sop_id,),
    ).fetchall()
    return {
        "id": row["ID"],
        "title": row["Title"],
        "purpose": row["Purpose"],
        "owner": row["Owner"],
        "revision": row["Revision"],
        "status": row["Status"],
        "createdAt": row["CreatedAt"],
        "updatedAt": row["UpdatedAt"],
        "steps": [
            {
                "id": step["ID"],
                "stepNumber": step["StepNumber"],
                "instruction": step["Instruction"],
            }
            for step in steps
        ],
        "attachments": [file_to_dict(item) for item in attachments],
    }


def parse_sop_payload(data):
    title = str(data.get("title") or "").strip()
    if not title:
        return None, "Title is required."
    status = str(data.get("status") or "draft").strip().lower()
    if status not in {"draft", "active"}:
        status = "draft"
    raw_steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    steps = []
    for item in raw_steps:
        if isinstance(item, str):
            instruction = item.strip()
        elif isinstance(item, dict):
            instruction = str(item.get("instruction") or "").strip()
        else:
            instruction = ""
        if instruction:
            steps.append(instruction)
    raw_ids = data.get("attachmentIds") if isinstance(data.get("attachmentIds"), list) else []
    attachment_ids = []
    for item in raw_ids:
        try:
            file_id = int(item)
        except (TypeError, ValueError):
            continue
        if file_id not in attachment_ids:
            attachment_ids.append(file_id)
    return {
        "title": title[:200],
        "purpose": str(data.get("purpose") or "").strip(),
        "owner": str(data.get("owner") or "").strip()[:120],
        "revision": str(data.get("revision") or "").strip()[:40],
        "status": status,
        "steps": steps,
        "attachmentIds": attachment_ids,
    }, None


def replace_sop_children(conn, sop_id, payload):
    conn.execute("DELETE FROM SopSteps WHERE SopID=?", (sop_id,))
    conn.execute("DELETE FROM SopAttachments WHERE SopID=?", (sop_id,))
    for index, instruction in enumerate(payload["steps"], start=1):
        conn.execute(
            "INSERT INTO SopSteps (SopID, StepNumber, Instruction) VALUES (?, ?, ?)",
            (sop_id, index, instruction),
        )
    for file_id in payload["attachmentIds"]:
        exists = conn.execute("SELECT ID FROM ToolkitFiles WHERE ID=?", (file_id,)).fetchone()
        if not exists:
            continue
        conn.execute(
            "INSERT INTO SopAttachments (SopID, FileID) VALUES (?, ?)",
            (sop_id, file_id),
        )
