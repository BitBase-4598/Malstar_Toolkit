from fastapi import APIRouter, Depends, Request

from logging_util import audit
from services.icb import (
    create_icb_station,
    delete_icb_station,
    import_icb_csv,
    list_icb_stations,
    update_icb_station,
)
from webutil import json_dict, query_int, read_upload, respond

router = APIRouter()


@router.get("/api/icb")
def list_icb(request: Request):
    q = str(request.query_params.get("q") or "")
    page = query_int(request, "page", 1)
    page_size = query_int(request, "pageSize", 100)
    payload = list_icb_stations(q, page, page_size)
    return respond({"success": True, **payload})


@router.post("/api/icb")
def create_icb(payload: dict = Depends(json_dict)):
    row, error = create_icb_station(payload)
    if error:
        audit("icb.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("icb.create", summary=f"{row['country']} / {row['icbCode'] or row['branch']}", resource_id=str(row["id"]))
    return respond({"success": True, "message": "ICB station created", "data": row}, 201)


@router.put("/api/icb/{record_id}")
def update_icb(record_id: int, payload: dict = Depends(json_dict)):
    row, error = update_icb_station(record_id, payload)
    if error:
        status = 404 if error == "Record not found" else 400
        audit("icb.update", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, status)
    audit("icb.update", summary=f"{row['country']} / {row['icbCode'] or row['branch']}", resource_id=str(row["id"]))
    return respond({"success": True, "message": "ICB station updated", "data": row})


@router.delete("/api/icb/{record_id}")
def delete_icb(record_id: int):
    row, error = delete_icb_station(record_id)
    if error:
        audit("icb.delete", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, 404)
    audit(
        "icb.delete",
        summary=f"{row['country']} / {row['icbCode'] or row['branch']}",
        resource_id=str(row["id"]),
    )
    return respond({"success": True, "message": "ICB station deleted", "data": row})


@router.post("/api/icb/import")
def import_icb(upload=Depends(read_upload)):
    if not upload:
        audit("icb.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    filename = filename or "icb.csv"
    result, error = import_icb_csv(filename, data)
    if error:
        audit("icb.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit("icb.import", summary=f"file={result['filename']} rows={result['rowCount']}")
    return respond({
        "success": True,
        "message": f"Imported {result['rowCount']} ICB station" + ("" if result["rowCount"] == 1 else "s"),
        "data": result,
    })
