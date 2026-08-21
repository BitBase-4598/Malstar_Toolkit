from flask import Blueprint, jsonify, request

from db import get_connection
from logging_util import log_event
from services.rag import index_sop, touch_index_state
from services.sops import load_sop, parse_sop_payload, replace_sop_children
from util import now_stamp

bp = Blueprint("sops", __name__)


@bp.get("/api/sops")
def list_sops():
    q = str(request.args.get("q") or "").strip()
    with get_connection() as conn:
        if q:
            rows = conn.execute(
                """
                SELECT * FROM Sops
                WHERE Title LIKE ? OR Owner LIKE ? OR Revision LIKE ?
                ORDER BY UpdatedAt DESC, ID DESC
                """,
                (f"%{q}%", f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM Sops ORDER BY UpdatedAt DESC, ID DESC").fetchall()
        data = []
        for row in rows:
            step_count = conn.execute(
                "SELECT COUNT(*) FROM SopSteps WHERE SopID=?", (row["ID"],)
            ).fetchone()[0]
            file_count = conn.execute(
                "SELECT COUNT(*) FROM SopAttachments WHERE SopID=?", (row["ID"],)
            ).fetchone()[0]
            data.append({
                "id": row["ID"],
                "title": row["Title"],
                "purpose": row["Purpose"],
                "owner": row["Owner"],
                "revision": row["Revision"],
                "status": row["Status"],
                "createdAt": row["CreatedAt"],
                "updatedAt": row["UpdatedAt"],
                "stepCount": step_count,
                "attachmentCount": file_count,
            })
    return jsonify({"success": True, "data": data})


@bp.post("/api/sops")
def create_sop():
    payload, error = parse_sop_payload(request.get_json(silent=True) or {})
    if error:
        log_event("SOP create failed", error)
        return jsonify({"success": False, "message": error}), 400
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
    log_event("SOP created", payload["title"])
    return jsonify({"success": True, "message": "SOP created", "data": data}), 201


@bp.get("/api/sops/<int:sop_id>")
def get_sop(sop_id):
    with get_connection() as conn:
        data = load_sop(conn, sop_id)
    if not data:
        return jsonify({"success": False, "message": "SOP not found"}), 404
    return jsonify({"success": True, "data": data})


@bp.put("/api/sops/<int:sop_id>")
def update_sop(sop_id):
    payload, error = parse_sop_payload(request.get_json(silent=True) or {})
    if error:
        log_event("SOP update failed", error)
        return jsonify({"success": False, "message": error}), 400
    with get_connection() as conn:
        existing = conn.execute("SELECT ID FROM Sops WHERE ID=?", (sop_id,)).fetchone()
        if not existing:
            return jsonify({"success": False, "message": "SOP not found"}), 404
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
    log_event("SOP updated", f"id={sop_id} {payload['title']}")
    return jsonify({"success": True, "message": "SOP saved", "data": data})


@bp.delete("/api/sops/<int:sop_id>")
def delete_sop(sop_id):
    with get_connection() as conn:
        row = conn.execute("SELECT Title FROM Sops WHERE ID=?", (sop_id,)).fetchone()
        if not row:
            return jsonify({"success": False, "message": "SOP not found"}), 404
        conn.execute("DELETE FROM RagChunks WHERE SourceType='sop' AND SourceID=?", (sop_id,))
        conn.execute("DELETE FROM SopSteps WHERE SopID=?", (sop_id,))
        conn.execute("DELETE FROM SopAttachments WHERE SopID=?", (sop_id,))
        conn.execute("DELETE FROM Sops WHERE ID=?", (sop_id,))
        touch_index_state(conn)
    log_event("SOP deleted", f"id={sop_id} {row['Title']}")
    return jsonify({"success": True, "message": "SOP deleted"})
