from fastapi import APIRouter, Depends, Request

from db import IntegrityError, get_connection
from logging_util import audit
from services.remarks import (
    collect_import_payloads,
    parse_payload,
    record_values,
    row_to_dict,
    upsert_imported_records,
)
from util import letters_only
from webutil import json_dict, query_int, respond

router = APIRouter()


@router.get("/api/customer-remarks")
def list_customer_remarks(request: Request):
    q_raw = str(request.query_params.get("q") or "").strip()
    q_letters = letters_only(q_raw)
    q_code = q_raw.upper()
    page = max(query_int(request, "page", 1), 1)
    page_size = min(max(query_int(request, "pageSize", 20), 1), 10000)
    clauses = []
    params = []
    if q_letters:
        clauses.append(
            """CustomerLetters != '' AND (
                   instr(CustomerLetters, ?) > 0
                   OR instr(?, CustomerLetters) > 0
               )"""
        )
        params.extend([q_letters, q_letters])
    if q_code:
        clauses.append("instr(upper(CTRLOrgcode), ?) > 0")
        params.append(q_code)
    where = f"WHERE {' OR '.join(f'({clause})' for clause in clauses)}" if clauses else ""
    with get_connection() as conn:
        if where:
            total = conn.execute(
                f"SELECT COUNT(*) FROM CustomerRemarks {where}", params
            ).fetchone()[0]
        else:
            total = conn.execute("SELECT COUNT(*) FROM CustomerRemarks").fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT ID, CTRLOrgcode, Customer, Remark1, Remark2, Remark3,
                   CreateTime, UpdateTime
            FROM CustomerRemarks {where}
            ORDER BY UpdateTime DESC, ID DESC LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
    return respond({
        "success": True,
        "data": [row_to_dict(row) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
    })


@router.post("/api/customer-remarks")
def create_customer_remark(payload: dict = Depends(json_dict)):
    payload, error = parse_payload(payload)
    if error:
        audit("record.create", "failure", summary=error)
        return respond({"success": False, "message": error}, 400)
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO CustomerRemarks
                    (CTRLOrgcode, Customer, CustomerLetters, Remark1, Remark2, Remark3)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                record_values(payload),
            )
            row = conn.execute(
                "SELECT * FROM CustomerRemarks WHERE ID=?", (cur.lastrowid,)
            ).fetchone()
    except IntegrityError:
        audit(
            "record.create",
            "failure",
            summary=f"duplicate {payload['ctrlOrgcode']} / {payload['customer']}",
        )
        return respond({
            "success": False,
            "message": "The CTRLOrgcode and Customer combination already exists.",
        }, 409)
    audit(
        "record.create",
        resource_id=row["ID"],
        summary=f"{payload['ctrlOrgcode']} / {payload['customer']}",
    )
    return respond({"success": True, "message": "Record created", "data": row_to_dict(row)}, 201)


@router.put("/api/customer-remarks/{record_id}")
def update_customer_remark(record_id: int, payload: dict = Depends(json_dict)):
    payload, error = parse_payload(payload)
    if error:
        audit("record.update", "failure", resource_id=record_id, summary=error)
        return respond({"success": False, "message": error}, 400)
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE CustomerRemarks
                SET CTRLOrgcode=?, Customer=?, CustomerLetters=?,
                    Remark1=?, Remark2=?, Remark3=?,
                    UpdateTime=CURRENT_TIMESTAMP
                WHERE ID=?
                """,
                record_values(payload) + (record_id,),
            )
            if cur.rowcount == 0:
                audit("record.update", "failure", resource_id=record_id, summary="not found")
                return respond({"success": False, "message": "Record not found"}, 404)
            row = conn.execute(
                "SELECT * FROM CustomerRemarks WHERE ID=?", (record_id,)
            ).fetchone()
    except IntegrityError:
        audit(
            "record.update",
            "failure",
            resource_id=record_id,
            summary=f"duplicate {payload['ctrlOrgcode']} / {payload['customer']}",
        )
        return respond({
            "success": False,
            "message": "The CTRLOrgcode and Customer combination already exists.",
        }, 409)
    audit(
        "record.update",
        resource_id=record_id,
        summary=f"{payload['ctrlOrgcode']} / {payload['customer']}",
    )
    return respond({"success": True, "message": "Record updated", "data": row_to_dict(row)})


@router.delete("/api/customer-remarks/{record_id}")
def delete_customer_remark(record_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM CustomerRemarks WHERE ID=?", (record_id,)).fetchone()
        cur = conn.execute("DELETE FROM CustomerRemarks WHERE ID=?", (record_id,))
    if cur.rowcount == 0:
        audit("record.delete", "failure", resource_id=record_id, summary="not found")
        return respond({"success": False, "message": "Record not found"}, 404)
    audit(
        "record.delete",
        resource_id=record_id,
        summary=f"{row['CTRLOrgcode']} / {row['Customer']}",
    )
    return respond({"success": True, "message": "Record deleted"})


@router.post("/api/customer-remarks/import")
def import_customer_remarks(data: dict = Depends(json_dict)):
    filename = str(data.get("filename") or "browser.csv")
    raw_rows = data.get("records")
    if not isinstance(raw_rows, list):
        audit("record.import", "failure", summary="JSON records missing")
        return respond({"success": False, "message": "No records were sent."}, 400)
    records, errors, duplicates = collect_import_payloads(raw_rows)
    if errors:
        audit(
            "record.import",
            "failure",
            summary=f"file={filename} validation errors={len(errors)}",
        )
        return respond({
            "success": False,
            "message": "CSV validation failed. Nothing was imported.",
            "errors": errors[:100],
        }, 400)
    if not records:
        audit("record.import", "failure", summary=f"file={filename} no data rows")
        return respond({"success": False, "message": "CSV contains no data rows."}, 400)
    created, updated = upsert_imported_records(records)
    audit(
        "record.import",
        summary=f"file={filename} processed={len(records)} created={created} updated={updated} duplicates={duplicates}",
    )
    return respond({
        "success": True,
        "message": "CSV import completed",
        "processed": len(records),
        "created": created,
        "updated": updated,
        "duplicates": duplicates,
    })
