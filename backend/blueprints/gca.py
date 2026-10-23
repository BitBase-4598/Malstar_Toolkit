from fastapi import APIRouter, Depends, Request

from logging_util import audit
from services.gca import (
    build_summary,
    import_gca_workbook,
    list_bookings,
    list_feedback,
    parse_date_arg,
)
from webutil import query_int, read_upload, respond

router = APIRouter()


def _dates(request: Request):
    date_from, error = parse_date_arg(request.query_params.get("dateFrom"))
    if error:
        return None, None, error
    date_to, error = parse_date_arg(request.query_params.get("dateTo"))
    if error:
        return None, None, error
    return date_from, date_to, None


@router.get("/api/gca/summary")
def gca_summary(request: Request):
    date_from, date_to, error = _dates(request)
    if error:
        return respond({"success": False, "message": error}, 400)
    data = build_summary(date_from, date_to, request.query_params.get("lane"))
    return respond({"success": True, "data": data})


@router.get("/api/gca/bookings")
def gca_bookings(request: Request):
    date_from, date_to, error = _dates(request)
    if error:
        return respond({"success": False, "message": error}, 400)
    payload = list_bookings(
        date_from,
        date_to,
        request.query_params.get("lane"),
        request.query_params.get("q") or "",
        query_int(request, "page", 1),
        query_int(request, "pageSize", 50),
    )
    return respond({"success": True, **payload})


@router.get("/api/gca/feedback")
def gca_feedback(request: Request):
    date_from, date_to, error = _dates(request)
    if error:
        return respond({"success": False, "message": error}, 400)
    payload = list_feedback(
        date_from,
        date_to,
        request.query_params.get("lane"),
        request.query_params.get("q") or "",
        query_int(request, "page", 1),
        query_int(request, "pageSize", 50),
    )
    return respond({"success": True, **payload})


@router.post("/api/gca/import")
def gca_import(upload=Depends(read_upload)):
    if not upload:
        audit("gca.import", "failure", summary="no file uploaded")
        return respond({"success": False, "message": "No file was uploaded."}, 400)
    filename, data = upload
    filename = filename or "gca.xlsx"
    result, error = import_gca_workbook(filename, data)
    if error:
        audit("gca.import", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    audit(
        "gca.import",
        summary=f"file={result['filename']} bookings={result['bookingCount']} feedback={result['feedbackCount']}",
    )
    return respond({
        "success": True,
        "message": (
            f"Imported {result['bookingCount']} booking"
            + ("" if result["bookingCount"] == 1 else "s")
            + f" and {result['feedbackCount']} feedback row"
            + ("" if result["feedbackCount"] == 1 else "s")
        ),
        "data": result,
    })
