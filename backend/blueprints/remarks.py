import csv
import io
import sqlite3

from flask import Blueprint, jsonify, request

from db import get_connection
from logging_util import audit
from services.remarks import (
    collect_import_payloads,
    parse_payload,
    record_values,
    row_to_dict,
    upsert_imported_records,
)
from util import letters_only

bp = Blueprint("remarks", __name__)


@bp.get("/api/customer-remarks")
def list_records():
    q_letters = letters_only(request.args.get("q", ""))
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("pageSize", 20, type=int), 1), 10000)
    if q_letters:
        where = """WHERE CustomerLetters != '' AND (
                       instr(CustomerLetters, ?) > 0
                       OR instr(?, CustomerLetters) > 0
                   )"""
        params = [q_letters, q_letters]
    else:
        where = ""
        params = []
    with get_connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM CustomerRemarks {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM CustomerRemarks {where}
            ORDER BY UpdateTime DESC, ID DESC LIMIT ? OFFSET ?
            """,
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
    return jsonify({
        "success": True,
        "data": [row_to_dict(row) for row in rows],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": max((total + page_size - 1) // page_size, 1),
        },
    })


@bp.post("/api/customer-remarks")
def create_record():
    payload, error = parse_payload(request.get_json(silent=True) or {})
    if error:
        audit("record.create", "failure", summary=error)
        return jsonify({"success": False, "message": error}), 400
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
    except sqlite3.IntegrityError:
        audit(
            "record.create",
            "failure",
            summary=f"duplicate {payload['ctrlOrgcode']} / {payload['customer']}",
        )
        return jsonify({
            "success": False,
            "message": "The CTRLOrgcode and Customer combination already exists.",
        }), 409
    audit(
        "record.create",
        resource_id=row["ID"],
        summary=f"{payload['ctrlOrgcode']} / {payload['customer']}",
    )
    return jsonify({"success": True, "message": "Record created", "data": row_to_dict(row)}), 201


@bp.put("/api/customer-remarks/<int:record_id>")
def update_record(record_id):
    payload, error = parse_payload(request.get_json(silent=True) or {})
    if error:
        audit("record.update", "failure", resource_id=record_id, summary=error)
        return jsonify({"success": False, "message": error}), 400
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
                return jsonify({"success": False, "message": "Record not found"}), 404
            row = conn.execute(
                "SELECT * FROM CustomerRemarks WHERE ID=?", (record_id,)
            ).fetchone()
    except sqlite3.IntegrityError:
        audit(
            "record.update",
            "failure",
            resource_id=record_id,
            summary=f"duplicate {payload['ctrlOrgcode']} / {payload['customer']}",
        )
        return jsonify({
            "success": False,
            "message": "The CTRLOrgcode and Customer combination already exists.",
        }), 409
    audit(
        "record.update",
        resource_id=record_id,
        summary=f"{payload['ctrlOrgcode']} / {payload['customer']}",
    )
    return jsonify({"success": True, "message": "Record updated", "data": row_to_dict(row)})


@bp.delete("/api/customer-remarks/<int:record_id>")
def delete_record(record_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM CustomerRemarks WHERE ID=?", (record_id,)).fetchone()
        cur = conn.execute("DELETE FROM CustomerRemarks WHERE ID=?", (record_id,))
    if cur.rowcount == 0:
        audit("record.delete", "failure", resource_id=record_id, summary="not found")
        return jsonify({"success": False, "message": "Record not found"}), 404
    audit(
        "record.delete",
        resource_id=record_id,
        summary=f"{row['CTRLOrgcode']} / {row['Customer']}",
    )
    return jsonify({"success": True, "message": "Record deleted"})


@bp.post("/api/customer-remarks/import")
def import_records():
    data = request.get_json(silent=True) or {}
    filename = str(data.get("filename") or "browser.csv")
    raw_rows = data.get("records")
    if not isinstance(raw_rows, list):
        audit("record.import", "failure", summary="JSON records missing")
        return jsonify({"success": False, "message": "No records were sent."}), 400
    records, errors, duplicates = collect_import_payloads(raw_rows)
    if errors:
        audit(
            "record.import",
            "failure",
            summary=f"file={filename} validation errors={len(errors)}",
        )
        return jsonify({
            "success": False,
            "message": "CSV validation failed. Nothing was imported.",
            "errors": errors[:100],
        }), 400
    if not records:
        audit("record.import", "failure", summary=f"file={filename} no data rows")
        return jsonify({"success": False, "message": "CSV contains no data rows."}), 400
    created, updated = upsert_imported_records(records)
    audit(
        "record.import",
        summary=f"file={filename} processed={len(records)} created={created} updated={updated} duplicates={duplicates}",
    )
    return jsonify({
        "success": True,
        "message": "CSV import completed",
        "processed": len(records),
        "created": created,
        "updated": updated,
        "duplicates": duplicates,
    })


@bp.post("/api/customer-remarks/import-csv")
def import_csv():
    if "file" not in request.files:
        audit("record.import", "failure", summary="no file uploaded")
        return jsonify({"success": False, "message": "No CSV file was uploaded."}), 400
    file = request.files["file"]
    filename = file.filename or ""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        audit("record.import", "failure", summary=f"file={filename} not a csv")
        return jsonify({"success": False, "message": "Please select a .csv file."}), 400
    try:
        reader = csv.DictReader(io.TextIOWrapper(file.stream, encoding="utf-8-sig", newline=""))
        if not reader.fieldnames:
            return jsonify({"success": False, "message": "CSV header row is missing."}), 400
        headers = {str(h).strip().lower(): h for h in reader.fieldnames if h}
        required = ["ctrlorgcode", "customer"]
        missing = [h for h in required if h not in headers]
        if missing:
            return jsonify({
                "success": False,
                "message": "Missing CSV column(s): " + ", ".join(missing),
            }), 400

        def value(row, name):
            original = headers.get(name.lower())
            return row.get(original, "") if original else ""

        raw_rows = []
        for row in reader:
            if not any(str(v or "").strip() for v in row.values()):
                continue
            raw_rows.append({
                "ctrlOrgcode": value(row, "ctrlorgcode"),
                "customer": value(row, "customer"),
                "remark1": value(row, "remark1"),
                "remark2": value(row, "remark2"),
                "remark3": value(row, "remark3"),
            })
        records, errors, duplicates = collect_import_payloads(raw_rows)

        if errors:
            audit(
                "record.import",
                "failure",
                summary=f"file={filename} validation errors={len(errors)}",
            )
            return jsonify({
                "success": False,
                "message": "CSV validation failed. Nothing was imported.",
                "errors": errors[:100],
            }), 400
        if not records:
            audit("record.import", "failure", summary=f"file={filename} no data rows")
            return jsonify({"success": False, "message": "CSV contains no data rows."}), 400

        created, updated = upsert_imported_records(records)
        audit(
            "record.import",
            summary=f"file={filename} processed={len(records)} created={created} updated={updated} duplicates={duplicates}",
        )
        return jsonify({
            "success": True,
            "message": "CSV import completed",
            "processed": len(records),
            "created": created,
            "updated": updated,
            "duplicates": duplicates,
        })
    except UnicodeDecodeError:
        audit("record.import", "failure", summary=f"file={filename} encoding error")
        return jsonify({
            "success": False,
            "message": "Please save the CSV with UTF-8 encoding.",
        }), 400
    except csv.Error as error:
        audit("record.import", "failure", summary=f"file={filename} {error}")
        return jsonify({"success": False, "message": f"Invalid CSV: {error}"}), 400
