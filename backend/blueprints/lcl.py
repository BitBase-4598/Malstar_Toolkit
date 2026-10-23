from fastapi import APIRouter, Depends, Request

from logging_util import audit
from services.lcl import (
    build_dashboard,
    build_map,
    build_summary,
    import_lcl_workbook,
    list_filter_options,
    split_csv_param,
)
from webutil import read_upload, respond

router = APIRouter()


@router.get("/api/lcl/filters")
def lcl_filters():
    return respond({"success": True, "data": list_filter_options()})


@router.get("/api/lcl/dashboard")
def lcl_dashboard(request: Request):
    return respond({"success": True, "data": build_dashboard(request.query_params)})


@router.get("/api/lcl/summary")
def lcl_summary(request: Request):
    return respond({"success": True, "data": build_summary(request.query_params)})


@router.get("/api/lcl/map")
def lcl_map(request: Request):
    include_arrows = bool(split_csv_param(request.query_params.get("direction")))
    return respond({"success": True, "data": build_map(request.query_params, include_arrows=include_arrows)})


@router.post("/api/lcl/import")
def lcl_import(upload=Depends(read_upload)):
    if not upload:
        audit("lcl.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    filename = filename or "lcl.xlsx"
    result, error = import_lcl_workbook(filename, data)
    if error:
        audit("lcl.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit(
        "lcl.import",
        summary=(
            f"{result['filename']} export={result['exportCount']} import={result['importCount']} "
            f"inserted={result.get('inserted', 0)} updated={result.get('updated', 0)}"
        ),
    )
    inserted = result.get("inserted", 0)
    updated = result.get("updated", 0)
    stored = result.get("storedTotal", result["total"])
    if updated:
        message = (
            f"Saved {result['total']:,} LCL shipments ({inserted:,} new, {updated:,} updated). "
            f"Dashboard now has {stored:,}."
        )
    else:
        message = f"Saved {result['total']:,} LCL shipments to the database"
    return respond({
        "success": True,
        "message": message,
        "data": result,
    })
