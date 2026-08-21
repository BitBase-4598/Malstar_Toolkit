from datetime import datetime

from db import get_connection
from util import letters_only, now_stamp


def parse_payload(data):
    ctrl_orgcode = str(data.get("ctrlOrgcode", data.get("CTRLOrgcode", "")) or "").strip().upper()
    customer = str(data.get("customer", data.get("Customer", "")) or "").strip()
    if not ctrl_orgcode:
        return None, "CTRLOrgcode is required."
    if not customer:
        return None, "Customer is required."
    return {
        "ctrlOrgcode": ctrl_orgcode,
        "customer": customer,
        "customerLetters": letters_only(customer),
        "remark1": str(data.get("remark1", data.get("Remark1", "")) or "").strip(),
        "remark2": str(data.get("remark2", data.get("Remark2", "")) or "").strip(),
        "remark3": str(data.get("remark3", data.get("Remark3", "")) or "").strip(),
    }, None


def row_to_dict(row):
    return {
        "id": row["ID"],
        "ctrlOrgcode": row["CTRLOrgcode"],
        "customer": row["Customer"],
        "remark1": row["Remark1"],
        "remark2": row["Remark2"],
        "remark3": row["Remark3"],
        "createTime": row["CreateTime"],
        "updateTime": row["UpdateTime"],
    }


def record_values(payload):
    return (
        payload["ctrlOrgcode"],
        payload["customer"],
        payload["customerLetters"],
        payload["remark1"],
        payload["remark2"],
        payload["remark3"],
    )


def upsert_imported_records(records):
    created = updated = 0
    with get_connection() as conn:
        for payload in records:
            existing = conn.execute(
                """
                SELECT ID FROM CustomerRemarks
                WHERE CTRLOrgcode=? AND Customer=?
                """,
                (payload["ctrlOrgcode"], payload["customer"]),
            ).fetchone()
            if existing:
                updated += 1
                conn.execute(
                    """
                    UPDATE CustomerRemarks
                    SET CustomerLetters=?, Remark1=?, Remark2=?, Remark3=?,
                        UpdateTime=CURRENT_TIMESTAMP WHERE ID=?
                    """,
                    (
                        payload["customerLetters"],
                        payload["remark1"],
                        payload["remark2"],
                        payload["remark3"],
                        existing["ID"],
                    ),
                )
            else:
                created += 1
                conn.execute(
                    """
                    INSERT INTO CustomerRemarks
                        (CTRLOrgcode, Customer, CustomerLetters, Remark1, Remark2, Remark3)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    record_values(payload),
                )
    return created, updated


def collect_import_payloads(raw_rows):
    records_by_key, errors, duplicates = {}, [], 0
    for row_no, raw in enumerate(raw_rows, start=2):
        if not any(str(v or "").strip() for v in raw.values()):
            continue
        payload, error = parse_payload(raw)
        if error:
            errors.append({"row": row_no, "message": error})
            continue
        key = (payload["ctrlOrgcode"].casefold(), payload["customer"].casefold())
        if key in records_by_key:
            duplicates += 1
        records_by_key[key] = payload
    return list(records_by_key.values()), errors, duplicates
