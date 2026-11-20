import csv
import re
from io import BytesIO, StringIO
from pathlib import Path

from openpyxl import load_workbook

from db import get_connection
from util import letters_only, now_stamp

# Header text from 源数据_TW. Extra columns are ignored.
COLUMNS = (
    ("Shipper", "shipper"),
    ("Shipper Full Name", "shipperName"),
    ("Consignee", "consignee"),
    ("Consignee Full Name", "consigneeName"),
    ("Origin", "origin"),
    ("Dest.", "dest"),
    ("Incoterm", "incoterm"),
    ("Svc. lvl.", "svcLevel"),
    ("HBL Dlv. Mode", "hblMode"),
    ("Pickup CFS", "pickupCfs"),
    ("Pickup Agent", "pickupAgent"),
    ("Dlv. Agent", "deliveryAgent"),
    ("Controlling Agent", "controllingAgent"),
    ("Controlling Customer", "controllingCustomer"),
    ("Shipment Stackability", "stackability"),
    ("Business Unit", "businessUnit"),
    ("Planned Discharge", "plannedDischarge"),
    ("Shipment ID", "shipmentId"),
    ("Consignee Address", "consigneeAddressBlob"),
    ("Consignee Address 1", "cnAddress1"),
    ("CN Address 2", "cnAddress2"),
    ("CN City", "cnCity"),
    ("CN State", "cnState"),
    ("CN Country/Region", "cnCountry"),
    ("Consignor Address 1", "crAddress1"),
    ("CR Address 2", "crAddress2"),
    ("CR City", "crCity"),
    ("CR State", "crState"),
    ("CR Country/Region", "crCountry"),
)

GROUP_KEYS = (
    "shipper",
    "shipperName",
    "shipperAddress",
    "consignee",
    "consigneeName",
    "consigneeAddress",
    "origin",
    "dest",
    "incoterm",
    "svcLevel",
    "hblMode",
    "pickupCfs",
    "pickupAgent",
    "deliveryAgent",
    "controllingAgent",
    "controllingCustomer",
    "stackability",
    "businessUnit",
    "plannedDischarge",
)

SELECT_SQL = """
    SELECT ShipmentId, Shipper, ShipperName, Consignee, ConsigneeName,
           Origin, Dest, Incoterm, SvcLevel, HblMode, PickupCfs, PickupAgent,
           DeliveryAgent, ControllingAgent, ControllingCustomer, Stackability,
           BusinessUnit, PlannedDischarge, ShipperAddress, ConsigneeAddress
    FROM TwPrefillShipments
"""

COMBO_LIMIT = 8


def normalize_header(value):
    text = str(value or "").strip().lower().replace("\ufeff", "")
    return re.sub(r"\s+", " ", text)


def clean_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).replace("\u00a0", " ").replace("\ufeff", "")
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split())


def join_parts(parts):
    out = []
    seen = set()
    for part in parts:
        text = clean_text(part)
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return ", ".join(out)


def confidence_label(count, total):
    if total <= 0 or count <= 0:
        return ""
    share = count / total
    if share >= 0.8 and count >= 10:
        return "高"
    if share >= 0.5:
        return "中高"
    return "参考"


def map_headers(raw_header):
    found = {}
    for index, cell in enumerate(raw_header or []):
        key = normalize_header(cell)
        for label, name in COLUMNS:
            if key == normalize_header(label) and name not in found:
                found[name] = index
    missing = [label for label, name in COLUMNS if name not in found]
    return found, missing


def records_from_rows(mapping, rows):
    records = []

    def col(raw, name):
        index = mapping.get(name)
        if index is None or index >= len(raw):
            return ""
        return clean_text(raw[index])

    for raw in rows:
        if raw is None:
            continue
        raw = list(raw)
        if not any(clean_text(cell) for cell in raw):
            continue
        shipper_name = col(raw, "shipperName")
        consignee_name = col(raw, "consigneeName")
        structured = [
            col(raw, "cnAddress1"),
            col(raw, "cnAddress2"),
            col(raw, "cnCity"),
            col(raw, "cnState"),
            col(raw, "cnCountry"),
        ]
        consignee_address = join_parts(structured) or col(raw, "consigneeAddressBlob")
        shipper_address = join_parts(
            [
                col(raw, "crAddress1"),
                col(raw, "crAddress2"),
                col(raw, "crCity"),
                col(raw, "crState"),
                col(raw, "crCountry"),
            ]
        )
        record = {
            "shipmentId": col(raw, "shipmentId"),
            "shipper": col(raw, "shipper").upper(),
            "shipperName": shipper_name,
            "shipperLetters": letters_only(shipper_name),
            "consignee": col(raw, "consignee").upper(),
            "consigneeName": consignee_name,
            "consigneeLetters": letters_only(consignee_name),
            "origin": col(raw, "origin").upper(),
            "dest": col(raw, "dest").upper(),
            "incoterm": col(raw, "incoterm").upper(),
            "svcLevel": col(raw, "svcLevel").upper(),
            "hblMode": col(raw, "hblMode"),
            "pickupCfs": col(raw, "pickupCfs").upper(),
            "pickupAgent": col(raw, "pickupAgent").upper(),
            "deliveryAgent": col(raw, "deliveryAgent").upper(),
            "controllingAgent": col(raw, "controllingAgent").upper(),
            "controllingCustomer": col(raw, "controllingCustomer").upper(),
            "stackability": col(raw, "stackability"),
            "businessUnit": col(raw, "businessUnit"),
            "plannedDischarge": col(raw, "plannedDischarge").upper(),
            "shipperAddress": shipper_address,
            "consigneeAddress": consignee_address,
        }
        if not any(record[key] for key in ("shipper", "shipperName", "consignee", "consigneeName", "origin", "dest")):
            continue
        records.append(record)
    return records


def parse_table(raw_header, rows):
    mapping, missing = map_headers(raw_header)
    if missing:
        return None, "Missing columns: " + ", ".join(missing)
    records = records_from_rows(mapping, rows)
    if not records:
        return None, "File contains no rows."
    return records, None


def decode_csv(data):
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_csv(data):
    text = decode_csv(data)
    if not text.strip():
        return None, "CSV is empty."
    reader = csv.reader(StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        return None, "CSV header row is missing."
    return parse_table(raw_header, reader)


def _row_values(item):
    return (
        item["shipmentId"],
        item["shipper"],
        item["shipperName"],
        item["shipperLetters"],
        item["consignee"],
        item["consigneeName"],
        item["consigneeLetters"],
        item["origin"],
        item["dest"],
        item["incoterm"],
        item["svcLevel"],
        item["hblMode"],
        item["pickupCfs"],
        item["pickupAgent"],
        item["deliveryAgent"],
        item["controllingAgent"],
        item["controllingCustomer"],
        item["stackability"],
        item["businessUnit"],
        item["plannedDischarge"],
        item["shipperAddress"],
        item["consigneeAddress"],
    )


def _content_key(item):
    return _row_values(item)[1:]


def append_records(filename, records):
    stamp = now_stamp()
    stored_name = (filename or "tw-prefill.csv")[:200]
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_ids = {
            row["ShipmentId"]
            for row in conn.execute(
                "SELECT ShipmentId FROM TwPrefillShipments WHERE ShipmentId != ''"
            )
        }
        existing_blank = {
            (
                row["Shipper"], row["ShipperName"], row["ShipperLetters"],
                row["Consignee"], row["ConsigneeName"], row["ConsigneeLetters"],
                row["Origin"], row["Dest"], row["Incoterm"], row["SvcLevel"], row["HblMode"],
                row["PickupCfs"], row["PickupAgent"], row["DeliveryAgent"],
                row["ControllingAgent"], row["ControllingCustomer"], row["Stackability"],
                row["BusinessUnit"], row["PlannedDischarge"],
                row["ShipperAddress"], row["ConsigneeAddress"],
            )
            for row in conn.execute(
                """
                SELECT Shipper, ShipperName, ShipperLetters, Consignee, ConsigneeName,
                       ConsigneeLetters, Origin, Dest, Incoterm, SvcLevel, HblMode,
                       PickupCfs, PickupAgent, DeliveryAgent, ControllingAgent,
                       ControllingCustomer, Stackability, BusinessUnit, PlannedDischarge,
                       ShipperAddress, ConsigneeAddress
                FROM TwPrefillShipments WHERE ShipmentId = ''
                """
            )
        }
        seen_ids = set()
        seen_blank = set()
        fresh = []
        skipped = 0
        for item in records:
            shipment_id = item["shipmentId"]
            if shipment_id:
                if shipment_id in existing_ids or shipment_id in seen_ids:
                    skipped += 1
                    continue
                seen_ids.add(shipment_id)
            else:
                key = _content_key(item)
                if key in existing_blank or key in seen_blank:
                    skipped += 1
                    continue
                seen_blank.add(key)
            fresh.append(_row_values(item))
        if fresh:
            conn.executemany(
                """
                INSERT INTO TwPrefillShipments (
                    ShipmentId, Shipper, ShipperName, ShipperLetters,
                    Consignee, ConsigneeName, ConsigneeLetters,
                    Origin, Dest, Incoterm, SvcLevel, HblMode,
                    PickupCfs, PickupAgent, DeliveryAgent,
                    ControllingAgent, ControllingCustomer, Stackability,
                    BusinessUnit, PlannedDischarge, ShipperAddress, ConsigneeAddress
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fresh,
            )
        total = conn.execute("SELECT COUNT(*) FROM TwPrefillShipments").fetchone()[0]
        conn.execute(
            """
            INSERT INTO TwPrefillMeta (ID, Filename, ImportedAt, RowCount)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(ID) DO UPDATE SET
                Filename=excluded.Filename,
                ImportedAt=excluded.ImportedAt,
                RowCount=excluded.RowCount
            """,
            (stored_name, stamp, total),
        )
    return {
        "filename": stored_name,
        "rowCount": total,
        "added": len(fresh),
        "skipped": skipped,
        "importedAt": stamp,
    }


def import_tw_prefill_csv(filename, data):
    records, error = parse_csv(data)
    if error:
        return None, error
    return append_records(filename, records), None


def import_tw_prefill_xlsx(path):
    path = Path(path)
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["源数据_TW"] if "源数据_TW" in workbook.sheetnames else workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)
        try:
            raw_header = next(rows)
        except StopIteration:
            return None, "Excel header row is missing."
        records, error = parse_table(raw_header, rows)
    finally:
        workbook.close()
    if error:
        return None, error
    return append_records(path.name, records), None


def meta_dict(conn):
    row = conn.execute("SELECT Filename, ImportedAt, RowCount FROM TwPrefillMeta WHERE ID=1").fetchone()
    if not row:
        return {"filename": "", "importedAt": "", "rowCount": 0}
    return {"filename": row["Filename"], "importedAt": row["ImportedAt"], "rowCount": row["RowCount"]}


def _row_dict(row):
    return {
        "shipmentId": row["ShipmentId"],
        "shipper": row["Shipper"],
        "shipperName": row["ShipperName"],
        "consignee": row["Consignee"],
        "consigneeName": row["ConsigneeName"],
        "origin": row["Origin"],
        "dest": row["Dest"],
        "incoterm": row["Incoterm"],
        "svcLevel": row["SvcLevel"],
        "hblMode": row["HblMode"],
        "pickupCfs": row["PickupCfs"],
        "pickupAgent": row["PickupAgent"],
        "deliveryAgent": row["DeliveryAgent"],
        "controllingAgent": row["ControllingAgent"],
        "controllingCustomer": row["ControllingCustomer"],
        "stackability": row["Stackability"],
        "businessUnit": row["BusinessUnit"],
        "plannedDischarge": row["PlannedDischarge"],
        "shipperAddress": row["ShipperAddress"],
        "consigneeAddress": row["ConsigneeAddress"],
    }


def _code_clause(column, value, clauses, params):
    token = clean_text(value).upper()
    if not token:
        return
    clauses.append(f"instr(upper({column}), ?) > 0")
    params.append(token)


def _name_clause(column, value, clauses, params):
    token = letters_only(value)
    if not token:
        return
    clauses.append(
        f"({column} != '' AND (instr({column}, ?) > 0 OR instr(?, {column}) > 0))"
    )
    params.extend([token, token])


def suggest(shipper="", shipper_name="", consignee="", consignee_name="", origin="", dest=""):
    clauses = []
    params = []
    _code_clause("Shipper", shipper, clauses, params)
    _name_clause("ShipperLetters", shipper_name, clauses, params)
    _code_clause("Consignee", consignee, clauses, params)
    _name_clause("ConsigneeLetters", consignee_name, clauses, params)
    _code_clause("Origin", origin, clauses, params)
    _code_clause("Dest", dest, clauses, params)
    with get_connection() as conn:
        meta = meta_dict(conn)
        if not clauses:
            return {"total": 0, "combos": [], "fields": {}, "meta": meta}
        where = " WHERE " + " AND ".join(clauses)
        stored = conn.execute(SELECT_SQL + where, params).fetchall()
    rows = [_row_dict(row) for row in stored]
    total = len(rows)
    buckets = {}
    for row in rows:
        key = tuple(row[name] for name in GROUP_KEYS)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {name: row[name] for name in GROUP_KEYS}
            bucket["count"] = 0
            bucket["samples"] = []
            buckets[key] = bucket
        bucket["count"] += 1
        sample = row["shipmentId"]
        if sample and sample not in bucket["samples"] and len(bucket["samples"]) < 3:
            bucket["samples"].append(sample)
    combos = sorted(buckets.values(), key=lambda item: (-item["count"], item["shipper"], item["consignee"]))
    for combo in combos:
        combo["share"] = round(combo["count"] / total, 4) if total else 0
        combo["confidence"] = confidence_label(combo["count"], total)
    fields = {}
    for name in GROUP_KEYS:
        counts = {}
        for row in rows:
            value = row[name]
            if value:
                counts[value] = counts.get(value, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
        fields[name] = [
            {
                "value": value,
                "count": count,
                "share": round(count / total, 4) if total else 0,
                "confidence": confidence_label(count, total),
            }
            for value, count in ranked
        ]
    return {"total": total, "combos": combos[:COMBO_LIMIT], "fields": fields, "meta": meta}
