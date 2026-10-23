from fastapi import APIRouter, Depends, Request

from logging_util import audit
from services.delcl import (
    create_delcl,
    delete_delcl,
    import_delcl_file,
    list_delcl,
    update_delcl,
)
from webutil import json_dict, query_int, read_upload, respond

router = APIRouter()


def _label(row):
    return row.get("orgaCode") or row.get("consigneeName") or row.get("consignee") or "DE-LCL"


@router.get("/api/de-lcl")
def list_delcl_records(request: Request):
    q = str(request.query_params.get("q") or "")
    page = query_int(request, "page", 1)
    page_size = query_int(request, "pageSize", 50)
    payload = list_delcl(q, page, page_size)
    return respond({"success": True, **payload})


@router.post("/api/de-lcl")
def create_delcl_record(payload: dict = Depends(json_dict)):
    row, error = create_delcl(payload)
    if error:
        audit("delcl.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("delcl.create", summary=_label(row), resource_id=str(row["id"]))
    return respond({"success": True, "message": "DE-LCL created", "data": row}, 201)


@router.put("/api/de-lcl/{record_id}")
def update_delcl_record(record_id: int, payload: dict = Depends(json_dict)):
    row, error = update_delcl(record_id, payload)
    if error:
        status = 404 if error == "Record not found" else 400
        audit("delcl.update", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, status)
    audit("delcl.update", summary=_label(row), resource_id=str(row["id"]))
    return respond({"success": True, "message": "DE-LCL updated", "data": row})


@router.delete("/api/de-lcl/{record_id}")
def delete_delcl_record(record_id: int):
    row, error = delete_delcl(record_id)
    if error:
        audit("delcl.delete", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, 404)
    audit("delcl.delete", summary=_label(row), resource_id=str(row["id"]))
    return respond({"success": True, "message": "DE-LCL deleted", "data": row})


@router.post("/api/de-lcl/import")
def import_delcl_records(upload=Depends(read_upload)):
    if not upload:
        audit("delcl.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    filename = filename or "DE-LCL.xlsx"
    result, error = import_delcl_file(filename, data)
    if error:
        audit("delcl.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("delcl.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    return respond({
        "success": True,
        "message": f"Imported {result['rowCount']:,} DE-LCL" + ("" if result["rowCount"] == 1 else "s"),
        "data": result,
    })
