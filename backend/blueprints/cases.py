from io import BytesIO

from fastapi import APIRouter, Depends, Request

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
from webutil import attachment, file_download, file_or_json, json_dict, read_upload, respond

router = APIRouter()


@router.get("/api/cases")
def list_cases_route(request: Request):
    q = str(request.query_params.get("q") or "").strip()
    with get_connection() as conn:
        data = list_cases(conn, q)
    return respond({"success": True, "data": data})


@router.post("/api/cases")
def create_case_route(payload: dict = Depends(json_dict)):
    payload, error = parse_case_create(payload)
    if error:
        audit("case.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    with get_connection() as conn:
        data = create_case(conn, payload)
    audit("case.create", resource_id=data["id"], summary=case_heading(data))
    return respond({"success": True, "message": "Case created", "data": data}, 201)


@router.post("/api/cases/import")
def import_cases_route(upload=Depends(read_upload)):
    if not upload:
        audit("case.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    result, error = import_cases_file(filename, data)
    if error:
        audit("case.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit(
        "case.import",
        summary=f"file={filename} imported={result['imported']} skipped={result['skipped']}",
    )
    imported = result["imported"]
    skipped = result["skipped"]
    message = f"Imported {imported} case" + ("s" if imported != 1 else "")
    if skipped:
        message += f", skipped {skipped}"
    return respond({
        "success": True,
        "message": message,
        "imported": imported,
        "skipped": skipped,
        "errors": result["errors"],
    })


@router.get("/api/cases/template")
def cases_template():
    return attachment(
        BytesIO(TEMPLATE_CSV.encode("utf-8-sig")),
        "feedback-template.csv",
        "text/csv",
    )


@router.get("/api/cases/{case_id}")
def get_case_route(case_id: int):
    with get_connection() as conn:
        data = load_case(conn, case_id)
    if not data:
        return respond({"success": False, "message": "Case not found"}, 404)
    return respond({"success": True, "data": data})


@router.put("/api/cases/{case_id}")
def update_case_route(case_id: int, payload: dict = Depends(json_dict)):
    with get_connection() as conn:
        current = load_case(conn, case_id)
        if not current:
            audit("case.update", "failure", resource_id=case_id, summary="not found")
            return respond({"success": False, "message": "Case not found"}, 404)
        payload, error = parse_case_review(payload, current)
        if error:
            audit("case.update", "failure", resource_id=case_id, summary=error)
            return respond({"success": False, "message": error}, 400)
        data = update_case_review(conn, case_id, payload)
    audit("case.update", resource_id=case_id, summary=case_heading(data))
    return respond({"success": True, "message": "Case saved", "data": data})


@router.patch("/api/cases/{case_id}/status")
def patch_case_status(case_id: int, body: dict = Depends(json_dict)):
    status, error = parse_status(body.get("status"), default="")
    if error:
        audit("case.status", "failure", resource_id=case_id, summary=error)
        return respond({"success": False, "message": error}, 400)
    with get_connection() as conn:
        existing = conn.execute("SELECT ID FROM Cases WHERE ID=?", (case_id,)).fetchone()
        if not existing:
            audit("case.status", "failure", resource_id=case_id, summary="not found")
            return respond({"success": False, "message": "Case not found"}, 404)
        data = set_case_status(conn, case_id, status)
    audit("case.status", resource_id=case_id, summary=f"{case_heading(data)} → {status}")
    return respond({"success": True, "message": "Status updated", "data": data})


@router.delete("/api/cases/{case_id}")
def delete_case_route(case_id: int):
    with get_connection() as conn:
        data = load_case(conn, case_id)
        if not data:
            audit("case.delete", "failure", resource_id=case_id, summary="not found")
            return respond({"success": False, "message": "Case not found"}, 404)
        stored_names = case_file_disk_names(conn, case_id)
        conn.execute("DELETE FROM Cases WHERE ID=?", (case_id,))
    unlink_stored_files(stored_names)
    audit("case.delete", resource_id=case_id, summary=case_heading(data))
    return respond({"success": True, "message": "Case deleted"})


@router.get("/api/cases/{case_id}/files")
def list_case_files(case_id: int):
    with get_connection() as conn:
        data = load_case(conn, case_id)
    if not data:
        return respond({"success": False, "message": "Case not found"}, 404)
    return respond({"success": True, "data": data.get("files") or []})


def _store_case_upload(case_id, filename, data):
    record, error = save_case_file(case_id, filename, data)
    if error:
        status = 404 if error == "Case not found" else 400
        audit("case.file.upload", "failure", resource_id=case_id, summary=error)
        return respond({"success": False, "message": error}, status)
    audit(
        "case.file.upload",
        resource_id=case_id,
        summary=f"{record['originalName']} ({record['kind']})",
        extra={"fileId": record["id"]},
    )
    return respond({"success": True, "message": "File attached", "data": record}, 201)


@router.post("/api/cases/{case_id}/files")
def upload_case_file(case_id: int, incoming=Depends(file_or_json)):
    if incoming["kind"] == "file":
        return _store_case_upload(case_id, incoming["filename"], incoming["data"])
    if incoming["kind"] == "missing":
        audit("case.file.upload", "failure", resource_id=case_id, summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    data = incoming["data"]
    filename = str(data.get("filename") or "")
    raw = str(data.get("content") or data.get("contentBase64") or "")
    if not raw:
        audit("case.file.upload", "failure", resource_id=case_id, summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    payload, error = decode_json_upload(raw)
    if error:
        audit("case.file.upload", "failure", resource_id=case_id, summary=error)
        return respond({"success": False, "message": error}, 400)
    return _store_case_upload(case_id, filename, payload)


def _case_file_or_error(case_id, file_id):
    with get_connection() as conn:
        row, path = load_case_file(conn, case_id, file_id)
    if not row:
        return None, respond({"success": False, "message": "File not found"}, 404)
    if not path.is_file():
        return None, respond({"success": False, "message": "File is missing on disk"}, 404)
    return (row, path), None


@router.get("/api/cases/{case_id}/files/{file_id}/preview")
def preview_case_file_route(case_id: int, file_id: int):
    loaded, error = _case_file_or_error(case_id, file_id)
    if error:
        return error
    row, path = loaded
    try:
        preview, preview_error = preview_case_file(row, path, case_id)
    except Exception as exc:
        return respond({"success": False, "message": f"Could not preview this file. {exc}"}, 400)
    if preview_error:
        return respond({"success": False, "message": preview_error}, 400)
    return respond({"success": True, "data": preview})


@router.get("/api/cases/{case_id}/files/{file_id}/content")
def case_file_content(case_id: int, file_id: int):
    loaded, error = _case_file_or_error(case_id, file_id)
    if error:
        return error
    row, path = loaded
    if row["Kind"] != "image":
        return respond({
            "success": False,
            "message": "Inline preview is only available for pictures.",
        }, 400)
    return file_download(
        path,
        row["OriginalName"],
        media_type=image_mime_type(row["StoredName"]),
        inline=True,
    )


@router.get("/api/cases/{case_id}/files/{file_id}")
def download_case_file(case_id: int, file_id: int):
    loaded, error = _case_file_or_error(case_id, file_id)
    if error:
        return error
    row, path = loaded
    return file_download(path, row["OriginalName"])


@router.delete("/api/cases/{case_id}/files/{file_id}")
def delete_case_file(case_id: int, file_id: int):
    with get_connection() as conn:
        row, path = load_case_file(conn, case_id, file_id)
        if not row:
            audit("case.file.delete", "failure", resource_id=case_id, summary="not found")
            return respond({"success": False, "message": "File not found"}, 404)
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
    return respond({"success": True, "message": "File deleted"})
