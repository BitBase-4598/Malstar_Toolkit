from fastapi import APIRouter, Depends, Request

from logging_util import audit
from services.unloco import (
    create_unlocode,
    delete_unlocode,
    import_unloco_csv,
    list_unlocodes,
    update_unlocode,
)
from webutil import json_dict, query_int, read_upload, respond

router = APIRouter()


@router.get("/api/unlocode")
def list_unloco(request: Request):
    q = str(request.query_params.get("q") or "")
    page = query_int(request, "page", 1)
    page_size = query_int(request, "pageSize", 50)
    payload = list_unlocodes(q, page, page_size)
    return respond({"success": True, **payload})


@router.post("/api/unlocode")
def create_unloco(payload: dict = Depends(json_dict)):
    row, error = create_unlocode(payload)
    if error:
        audit("unloco.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit(
        "unloco.create",
        summary=f"{row['unCode'] or row['portName']} / {row['countryCode']}",
        resource_id=str(row["id"]),
    )
    return respond({"success": True, "message": "UNLOCODE created", "data": row}, 201)


@router.put("/api/unlocode/{record_id}")
def update_unloco(record_id: int, payload: dict = Depends(json_dict)):
    row, error = update_unlocode(record_id, payload)
    if error:
        status = 404 if error == "Record not found" else 400
        audit("unloco.update", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, status)
    audit(
        "unloco.update",
        summary=f"{row['unCode'] or row['portName']} / {row['countryCode']}",
        resource_id=str(row["id"]),
    )
    return respond({"success": True, "message": "UNLOCODE updated", "data": row})


@router.delete("/api/unlocode/{record_id}")
def delete_unloco(record_id: int):
    row, error = delete_unlocode(record_id)
    if error:
        audit("unloco.delete", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, 404)
    audit(
        "unloco.delete",
        summary=f"{row['unCode'] or row['portName']} / {row['countryCode']}",
        resource_id=str(row["id"]),
    )
    return respond({"success": True, "message": "UNLOCODE deleted", "data": row})


@router.post("/api/unlocode/import")
def import_unloco(upload=Depends(read_upload)):
    if not upload:
        audit("unloco.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    filename = filename or "UNLOCODE.csv"
    result, error = import_unloco_csv(filename, data)
    if error:
        audit("unloco.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("unloco.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    return respond({
        "success": True,
        "message": f"Imported {result['rowCount']:,} UNLOCODE" + ("" if result["rowCount"] == 1 else "s"),
        "data": result,
    })
