from fastapi import APIRouter, Depends, Request

from db import get_connection
from logging_util import audit
from services.rag import index_sop, touch_index_state
from services.sops import load_sop, parse_sop_payload, replace_sop_children
from util import now_stamp
from webutil import json_dict, respond

router = APIRouter()


@router.get("/api/sops")
def list_sops(request: Request):
    q = str(request.query_params.get("q") or "").strip()
    with get_connection() as conn:
        if q:
            rows = conn.execute(
                """
                SELECT
                    Sops.*,
                    COALESCE(steps.cnt, 0) AS StepCount,
                    COALESCE(files.cnt, 0) AS FileCount
                FROM Sops
                LEFT JOIN (
                    SELECT SopID, COUNT(*) AS cnt FROM SopSteps GROUP BY SopID
                ) steps ON steps.SopID = Sops.ID
                LEFT JOIN (
                    SELECT SopID, COUNT(*) AS cnt FROM SopAttachments GROUP BY SopID
                ) files ON files.SopID = Sops.ID
                WHERE Sops.Title LIKE ? OR Sops.Owner LIKE ? OR Sops.Revision LIKE ?
                ORDER BY Sops.UpdatedAt DESC, Sops.ID DESC
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    Sops.*,
                    COALESCE(steps.cnt, 0) AS StepCount,
                    COALESCE(files.cnt, 0) AS FileCount
                FROM Sops
                LEFT JOIN (
                    SELECT SopID, COUNT(*) AS cnt FROM SopSteps GROUP BY SopID
                ) steps ON steps.SopID = Sops.ID
                LEFT JOIN (
                    SELECT SopID, COUNT(*) AS cnt FROM SopAttachments GROUP BY SopID
                ) files ON files.SopID = Sops.ID
                ORDER BY Sops.UpdatedAt DESC, Sops.ID DESC
                """
            ).fetchall()
        data = [
            {
                "id": row["ID"],
                "title": row["Title"],
                "purpose": row["Purpose"],
                "owner": row["Owner"],
                "revision": row["Revision"],
                "status": row["Status"],
                "createdAt": row["CreatedAt"],
                "updatedAt": row["UpdatedAt"],
                "stepCount": row["StepCount"],
                "attachmentCount": row["FileCount"],
            }
            for row in rows
        ]
    return respond({"success": True, "data": data})


@router.post("/api/sops")
def create_sop(payload: dict = Depends(json_dict)):
    payload, error = parse_sop_payload(payload)
    if error:
        audit("sop.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    stamp = now_stamp()
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO Sops (Title, Purpose, Owner, Revision, Status, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"],
                payload["purpose"],
                payload["owner"],
                payload["revision"],
                payload["status"],
                stamp,
                stamp,
            ),
        )
        sop_id = cur.lastrowid
        replace_sop_children(conn, sop_id, payload)
        index_sop(conn, sop_id)
        data = load_sop(conn, sop_id)
    audit("sop.create", resource_id=sop_id, summary=payload["title"])
    return respond({"success": True, "message": "SOP created", "data": data}, 201)


@router.get("/api/sops/{sop_id}")
def get_sop(sop_id: int):
    with get_connection() as conn:
        data = load_sop(conn, sop_id)
    if not data:
        return respond({"success": False, "message": "SOP not found"}, 404)
    return respond({"success": True, "data": data})


@router.put("/api/sops/{sop_id}")
def update_sop(sop_id: int, payload: dict = Depends(json_dict)):
    payload, error = parse_sop_payload(payload)
    if error:
        audit("sop.update", "failure", resource_id=sop_id, summary=error)
        return respond({"success": False, "message": error}, 400)
    with get_connection() as conn:
        existing = conn.execute("SELECT ID FROM Sops WHERE ID=?", (sop_id,)).fetchone()
        if not existing:
            audit("sop.update", "failure", resource_id=sop_id, summary="not found")
            return respond({"success": False, "message": "SOP not found"}, 404)
        conn.execute(
            """
            UPDATE Sops
            SET Title=?, Purpose=?, Owner=?, Revision=?, Status=?, UpdatedAt=?
            WHERE ID=?
            """,
            (
                payload["title"],
                payload["purpose"],
                payload["owner"],
                payload["revision"],
                payload["status"],
                now_stamp(),
                sop_id,
            ),
        )
        replace_sop_children(conn, sop_id, payload)
        index_sop(conn, sop_id)
        data = load_sop(conn, sop_id)
    audit("sop.update", resource_id=sop_id, summary=payload["title"])
    return respond({"success": True, "message": "SOP saved", "data": data})


@router.delete("/api/sops/{sop_id}")
def delete_sop(sop_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT Title FROM Sops WHERE ID=?", (sop_id,)).fetchone()
        if not row:
            audit("sop.delete", "failure", resource_id=sop_id, summary="not found")
            return respond({"success": False, "message": "SOP not found"}, 404)
        conn.execute("DELETE FROM RagChunks WHERE SourceType='sop' AND SourceID=?", (sop_id,))
        conn.execute("DELETE FROM SopSteps WHERE SopID=?", (sop_id,))
        conn.execute("DELETE FROM SopAttachments WHERE SopID=?", (sop_id,))
        conn.execute("DELETE FROM Sops WHERE ID=?", (sop_id,))
        touch_index_state(conn)
    audit("sop.delete", resource_id=sop_id, summary=row["Title"])
    return respond({"success": True, "message": "SOP deleted"})
