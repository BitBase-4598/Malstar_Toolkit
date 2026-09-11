from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from db import get_connection
from logging_util import audit
from services.cases import (
    TEMPLATE_CSV,
    case_file_disk_names,
    case_heading,
    create_case,
    decode_json_upload,
    import_cases_file,
    list_cases,
    load_case,
    load_case_file,
    parse_case_create,
    parse_case_review,
    parse_status,
    preview_case_file,
    save_case_file,
    set_case_status,
    unlink_stored_files,
    update_case_review,
)
from services.files_store import image_mime_type, stored_path
from util import now_stamp

bp = Blueprint("cases", __name__)


@bp.get("/api/cases")
def list_cases_route():
    q = str(request.args.get("q") or "").strip()
    with get_connection() as conn:
        data = list_cases(conn, q)
    return jsonify({"success": True, "data": data})


@bp.post("/api/cases")
def create_case_route():
    payload, error = parse_case_create(request.get_json(silent=True) or {})
    if error:
        audit("case.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    with get_connection() as conn:
        data = create_case(conn, payload)
    audit("case.create", resource_id=data["id"], summary=case_heading(data))
    return jsonify({"success": True, "message": "Case created", "data": data}), 201


@bp.post("/api/cases/import")
def import_cases_route():
    if "file" not in request.files:
        audit("case.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or ""
    result, error = import_cases_file(filename, file.read())
    if error:
        audit("case.import", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
    audit(
        "case.import",
        summary=f"file={filename} imported={result['imported']} skipped={result['skipped']}",
    )
    imported = result["imported"]
    skipped = result["skipped"]
    message = f"Imported {imported} case" + ("s" if imported != 1 else "")
    if skipped:
        message += f", skipped {skipped}"
    return jsonify({
        "success": True,
        "message": message,
        "imported": imported,
        "skipped": skipped,
        "errors": result["errors"],
    })


@bp.get("/api/cases/template")
def cases_template():
    buffer = BytesIO(TEMPLATE_CSV.encode("utf-8-sig"))
    return send_file(
        buffer,
        as_attachment=True,
        download_name="feedback-template.csv",
        mimetype="text/csv",
    )


@bp.get("/api/cases/<int:case_id>")
def get_case_route(case_id):
    with get_connection() as conn:
        data = load_case(conn, case_id)
    if not data:
        return jsonify({"success": False, "message": "Case not found"}), 404
    return jsonify({"success": True, "data": data})


@bp.put("/api/cases/<int:case_id>")
def update_case_route(case_id):
    with get_connection() as conn:
        current = load_case(conn, case_id)
        if not current:
            audit("case.update", "failure", resource_id=case_id, summary="not found")
            return jsonify({"success": False, "message": "Case not found"}), 404
        payload, error = parse_case_review(request.get_json(silent=True) or {}, current)
        if error:
            audit("case.update", "failure", resource_id=case_id, summary=error)
            return jsonify({"success": False, "message": error}), 400
        data = update_case_review(conn, case_id, payload)
    audit("case.update", resource_id=case_id, summary=case_heading(data))
    return jsonify({"success": True, "message": "Case saved", "data": data})


@bp.patch("/api/cases/<int:case_id>/status")
def patch_case_status(case_id):
    body = request.get_json(silent=True) or {}
    status, error = parse_status(body.get("status"), default="")
    if error:
        audit("case.status", "failure", resource_id=case_id, summary=error)
        return jsonify({"success": False, "message": error}), 400
    with get_connection() as conn:
        existing = conn.execute("SELECT ID FROM Cases WHERE ID=?", (case_id,)).fetchone()
        if not existing:
            audit("case.status", "failure", resource_id=case_id, summary="not found")
            return jsonify({"success": False, "message": "Case not found"}), 404
        data = set_case_status(conn, case_id, status)
    audit("case.status", resource_id=case_id, summary=f"{case_heading(data)} → {status}")
    return jsonify({"success": True, "message": "Status updated", "data": data})


@bp.delete("/api/cases/<int:case_id>")
def delete_case_route(case_id):
    with get_connection() as conn:
        data = load_case(conn, case_id)
        if not data:
            audit("case.delete", "failure", resource_id=case_id, summary="not found")
            return jsonify({"success": False, "message": "Case not found"}), 404
        stored_names = case_file_disk_names(conn, case_id)
        conn.execute("DELETE FROM Cases WHERE ID=?", (case_id,))
    unlink_stored_files(stored_names)
    audit("case.delete", resource_id=case_id, summary=case_heading(data))
    return jsonify({"success": True, "message": "Case deleted"})


@bp.get("/api/cases/<int:case_id>/files")
def list_case_files(case_id):
    with get_connection() as conn:
        data = load_case(conn, case_id)
    if not data:
        return jsonify({"success": False, "message": "Case not found"}), 404
    return jsonify({"success": True, "data": data.get("files") or []})


def _store_case_upload(case_id, filename, data):
    record, error = save_case_file(case_id, filename, data)
    if error:
        status = 404 if error == "Case not found" else 400
        audit("case.file.upload", "failure", resource_id=case_id, summary=error)
        return jsonify({"success": False, "message": error}), status
    audit(
        "case.file.upload",
        resource_id=case_id,
        summary=f"{record['originalName']} ({record['kind']})",
        extra={"fileId": record["id"]},
    )
    return jsonify({"success": True, "message": "File attached", "data": record}), 201


@bp.post("/api/cases/<int:case_id>/files")
def upload_case_file(case_id):
    if "file" in request.files:
        file = request.files["file"]
        return _store_case_upload(case_id, file.filename or "", file.read())
    data = request.get_json(silent=True) or {}
    filename = str(data.get("filename") or "")
    raw = str(data.get("content") or data.get("contentBase64") or "")
    if not raw:
        audit("case.file.upload", "failure", resource_id=case_id, summary="no file uploaded")
        return jsonify({"success": False, "message": "No file was uploaded."}), 400
    payload, error = decode_json_upload(raw)
    if error:
        audit("case.file.upload", "failure", resource_id=case_id, summary=error)
        return jsonify({"success": False, "message": error}), 400
    return _store_case_upload(case_id, filename, payload)


def _case_file_or_error(case_id, file_id):
    with get_connection() as conn:
        row, path = load_case_file(conn, case_id, file_id)
    if not row:
        return None, (jsonify({"success": False, "message": "File not found"}), 404)
    if not path.is_file():
        return None, (jsonify({"success": False, "message": "File is missing on disk"}), 404)
    return (row, path), None


@bp.get("/api/cases/<int:case_id>/files/<int:file_id>/preview")
def preview_case_file_route(case_id, file_id):
    loaded, error = _case_file_or_error(case_id, file_id)
    if error:
        return error
    row, path = loaded
    try:
        preview, preview_error = preview_case_file(row, path, case_id)
    except Exception as exc:
        return jsonify({"success": False, "message": f"Could not preview this file. {exc}"}), 400
    if preview_error:
        return jsonify({"success": False, "message": preview_error}), 400
    return jsonify({"success": True, "data": preview})


@bp.get("/api/cases/<int:case_id>/files/<int:file_id>/content")
def case_file_content(case_id, file_id):
    loaded, error = _case_file_or_error(case_id, file_id)
    if error:
        return error
    row, path = loaded
    if row["Kind"] != "image":
        return jsonify({
            "success": False,
            "message": "Inline preview is only available for pictures.",
        }), 400
    return send_file(
        path,
        mimetype=image_mime_type(row["StoredName"]),
        as_attachment=False,
        download_name=row["OriginalName"],
    )


@bp.get("/api/cases/<int:case_id>/files/<int:file_id>")
def download_case_file(case_id, file_id):
    loaded, error = _case_file_or_error(case_id, file_id)
    if error:
        return error
    row, path = loaded
    return send_file(path, as_attachment=True, download_name=row["OriginalName"])


@bp.delete("/api/cases/<int:case_id>/files/<int:file_id>")
def delete_case_file(case_id, file_id):
    with get_connection() as conn:
        row, path = load_case_file(conn, case_id, file_id)
        if not row:
            audit("case.file.delete", "failure", resource_id=case_id, summary="not found")
            return jsonify({"success": False, "message": "File not found"}), 404
        conn.execute("DELETE FROM CaseFiles WHERE ID=? AND CaseID=?", (file_id, case_id))
        conn.execute(
            "UPDATE Cases SET UpdatedAt=? WHERE ID=?",
            (now_stamp(), case_id),
        )
        name = row["OriginalName"]
        stored_name = row["StoredName"]
    stored = stored_path(stored_name)
    if stored.is_file():
        stored.unlink()
    audit("case.file.delete", resource_id=case_id, summary=name, extra={"fileId": file_id})
    return jsonify({"success": True, "message": "File deleted"})
