from fastapi import APIRouter, Depends, Request

from logging_util import audit
from services.debosch import (
    create_debosch,
    delete_debosch,
    import_debosch_file,
    list_debosch,
    update_debosch,
)
from webutil import json_dict, query_int, read_upload, respond

router = APIRouter()


def _label(row):
    return row.get("organizationCode") or row.get("fullName") or "DE-BOSCH"


@router.get("/api/de-bosch")
def list_debosch_records(request: Request):
    q = str(request.query_params.get("q") or "")
    page = query_int(request, "page", 1)
    page_size = query_int(request, "pageSize", 50)
    payload = list_debosch(q, page, page_size)
    return respond({"success": True, **payload})


@router.post("/api/de-bosch")
def create_debosch_record(payload: dict = Depends(json_dict)):
    row, error = create_debosch(payload)
    if error:
        audit("debosch.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("debosch.create", summary=_label(row), resource_id=str(row["id"]))
    return respond({"success": True, "message": "DE-BOSCH created", "data": row}, 201)


@router.put("/api/de-bosch/{record_id}")
def update_debosch_record(record_id: int, payload: dict = Depends(json_dict)):
    row, error = update_debosch(record_id, payload)
    if error:
        status = 404 if error == "Record not found" else 400
        audit("debosch.update", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, status)
    audit("debosch.update", summary=_label(row), resource_id=str(row["id"]))
    return respond({"success": True, "message": "DE-BOSCH updated", "data": row})


@router.delete("/api/de-bosch/{record_id}")
def delete_debosch_record(record_id: int):
    row, error = delete_debosch(record_id)
    if error:
        audit("debosch.delete", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, 404)
    audit("debosch.delete", summary=_label(row), resource_id=str(row["id"]))
    return respond({"success": True, "message": "DE-BOSCH deleted", "data": row})


@router.post("/api/de-bosch/import")
def import_debosch_records(upload=Depends(read_upload)):
    if not upload:
        audit("debosch.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    filename = filename or "Bosch-DE.xlsx"
    result, error = import_debosch_file(filename, data)
    if error:
        audit("debosch.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("debosch.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    noun = "organization" if result["rowCount"] == 1 else "organizations"
    return respond({
        "success": True,
        "message": f"Imported {result['rowCount']:,} DE-BOSCH {noun}",
        "data": result,
    })
