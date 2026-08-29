import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from config import LCL_XLSX_PATH
from db import get_connection
from services.lcl_centroids import COUNTRY_CENTROIDS, COUNTRY_NAMES
from util import now_stamp

KEEP_FIELDS = {
    "Shipment ID": "shipment_id",
    "Job Branch": "job_branch",
    "Dest Ctry": "dest_ctry",
    "Weight": "weight",
    "Volume": "volume",
    "Dimension": "dimension",
    "Chargeable": "chargeable",
    "Shipment Controlling Party Name": "customer",
    "Direction": "direction",
    "Month Name": "month_name",
    "Count of Bosch": "bosch",
    "Year": "year",
    "Year Month": "year_month",
    "Country Full Name": "country_name",
}

MONTH_ORDER = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

DEFAULT_XLSX = Path(LCL_XLSX_PATH)

DIM_RE = re.compile(
    r"^\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*$"
)


def local_tag(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_dimension(raw):
    match = DIM_RE.match(str(raw or ""))
    if not match:
        return None, None, None, None
    pieces, length, width, height = (float(part) for part in match.groups())
    return pieces, length, width, height


def to_float(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_cache_item(elem):
    kind = local_tag(elem.tag)
    if kind == "s":
        return elem.get("v") or ""
    if kind == "n":
        return to_float(elem.get("v"))
    if kind in ("d", "e"):
        return elem.get("v") or ""
    if kind == "b":
        return 1 if str(elem.get("v") or "").lower() in ("1", "true") else 0
    if kind == "m":
        return None
    return elem.get("v")


def parse_cache_fields(xml_bytes):
    root = ET.fromstring(xml_bytes)
    fields = []
    for node in root.iter():
        if local_tag(node.tag) != "cacheField":
            continue
        items = []
        for child in list(node):
            if local_tag(child.tag) != "sharedItems":
                continue
            for item in list(child):
                items.append(parse_cache_item(item))
        fields.append({"name": node.get("name") or "", "items": items})
    return fields


def record_values(row_elem, fields):
    values = []
    children = [child for child in list(row_elem) if local_tag(child.tag) != "extLst"]
    for index, child in enumerate(children):
        kind = local_tag(child.tag)
        shared = fields[index]["items"] if index < len(fields) else []
        if kind == "x":
            try:
                pos = int(child.get("v") or 0)
            except ValueError:
                pos = 0
            values.append(shared[pos] if 0 <= pos < len(shared) else None)
        else:
            values.append(parse_cache_item(child))
    while len(values) < len(fields):
        values.append(None)
    return values


def slim_row(fields, values, fallback_direction):
    raw = {}
    for field, value in zip(fields, values):
        key = KEEP_FIELDS.get(field["name"])
        if key:
            raw[key] = value
    dest = to_text(raw.get("dest_ctry")).upper()
    if len(dest) > 2:
        dest = dest[:2]
    pieces, length, width, height = parse_dimension(raw.get("dimension"))
    bosch = to_float(raw.get("bosch")) or 0
    direction = to_text(raw.get("direction")) or fallback_direction
    return (
        to_text(raw.get("shipment_id")),
        direction,
        to_text(raw.get("year")),
        to_text(raw.get("month_name")),
        to_text(raw.get("year_month")),
        to_text(raw.get("job_branch")),
        dest,
        to_text(raw.get("country_name")) or COUNTRY_NAMES.get(dest, ""),
        to_text(raw.get("customer")),
        1 if bosch else 0,
        to_float(raw.get("weight")),
        to_float(raw.get("volume")),
        to_text(raw.get("dimension")),
        pieces,
        length,
        width,
        height,
        to_float(raw.get("chargeable")),
    )


INSERT_SQL = """
    INSERT INTO LclShipments (
        ShipmentID, Direction, Year, MonthName, YearMonth, JobBranch,
        DestCtry, CountryName, Customer, IsBosch, Weight, Volume,
        DimensionRaw, Pieces, DimL, DimW, DimH, Chargeable
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def flush_rows(conn, buffer):
    if not buffer:
        return 0
    conn.executemany(INSERT_SQL, buffer)
    conn.commit()
    count = len(buffer)
    buffer.clear()
    return count


def import_cache(zip_file, definition_name, records_name, direction, conn, batch):
    fields = parse_cache_fields(zip_file.read(definition_name))
    inserted = 0
    buffer = []
    with zip_file.open(records_name) as handle:
        context = ET.iterparse(handle, events=("start", "end"))
        root = None
        for event, elem in context:
            if event == "start":
                if root is None:
                    root = elem
                continue
            if local_tag(elem.tag) != "r":
                continue
            values = record_values(elem, fields)
            buffer.append(slim_row(fields, values, direction))
            root.remove(elem)
            if len(buffer) >= 2000:
                inserted += flush_rows(conn, buffer)
                if inserted % 20000 == 0:
                    print(f"  {direction}: {inserted:,}", flush=True)
    inserted += flush_rows(conn, buffer)
    return inserted


def import_lcl_workbook():
    source = Path(DEFAULT_XLSX)
    if not source.is_file():
        return None, f"Workbook not found: {source}"
    if source.suffix.lower() != ".xlsx":
        return None, "Please select the LCL .xlsx workbook."
    stamp = now_stamp()
    export_count = 0
    import_count = 0
    with zipfile.ZipFile(source) as archive:
        names = set(archive.namelist())
        if "xl/pivotCache/pivotCacheDefinition1.xml" not in names:
            return None, "This workbook has no LCL pivot cache."
        with get_connection() as conn:
            conn.execute("DELETE FROM LclShipments")
            conn.execute("DELETE FROM LclImportMeta")
            export_count = import_cache(
                archive,
                "xl/pivotCache/pivotCacheDefinition1.xml",
                "xl/pivotCache/pivotCacheRecords1.xml",
                "Export",
                conn,
                None,
            )
            if "xl/pivotCache/pivotCacheDefinition2.xml" in names:
                import_count = import_cache(
                    archive,
                    "xl/pivotCache/pivotCacheDefinition2.xml",
                    "xl/pivotCache/pivotCacheRecords2.xml",
                    "Import",
                    conn,
                    None,
                )
            conn.execute(
                """
                INSERT INTO LclImportMeta (ID, Filename, ImportedAt, ExportCount, ImportCount)
                VALUES (1, ?, ?, ?, ?)
                """,
                (source.name, stamp, export_count, import_count),
            )
    return {
        "filename": source.name,
        "importedAt": stamp,
        "exportCount": export_count,
        "importCount": import_count,
        "total": export_count + import_count,
    }, None


def split_csv_param(value):
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def build_filters(args):
    clauses = []
    params = []

    def add_in(column, values):
        vals = [item for item in values if item]
        if not vals:
            return
        placeholders = ",".join("?" * len(vals))
        clauses.append(f"{column} IN ({placeholders})")
        params.extend(vals)

    add_in("Year", split_csv_param(args.get("year")))
    add_in("MonthName", split_csv_param(args.get("month")))
    add_in("JobBranch", split_csv_param(args.get("branch")))
    add_in("Direction", split_csv_param(args.get("direction")))
    add_in("DestCtry", [item.upper() for item in split_csv_param(args.get("country"))])
    bosch = str(args.get("bosch") or "all").strip().lower()
    if bosch in ("yes", "1", "true"):
        clauses.append("IsBosch=1")
    elif bosch in ("no", "0", "false"):
        clauses.append("IsBosch=0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def distinct_values(conn, column):
    rows = conn.execute(
        f"""
        SELECT DISTINCT {column} FROM LclShipments
        WHERE {column} IS NOT NULL AND {column} != ''
        ORDER BY {column}
        """
    ).fetchall()
    return [row[0] for row in rows]


def list_filter_options():
    with get_connection() as conn:
        months = distinct_values(conn, "MonthName")
        months.sort(key=lambda name: MONTH_ORDER.index(name) if name in MONTH_ORDER else 99)
        meta = conn.execute("SELECT * FROM LclImportMeta WHERE ID=1").fetchone()
        countries = [
            {"code": row["DestCtry"], "name": row["CountryName"] or COUNTRY_NAMES.get(row["DestCtry"], row["DestCtry"])}
            for row in conn.execute(
                """
                SELECT DestCtry, MAX(CountryName) AS CountryName, COUNT(*) AS N
                FROM LclShipments
                WHERE DestCtry != ''
                GROUP BY DestCtry
                ORDER BY N DESC, DestCtry
                """
            ).fetchall()
        ]
        return {
            "years": distinct_values(conn, "Year"),
            "months": months,
            "branches": distinct_values(conn, "JobBranch"),
            "directions": distinct_values(conn, "Direction"),
            "countries": countries,
            "meta": {
                "filename": meta["Filename"] if meta else "",
                "importedAt": meta["ImportedAt"] if meta else "",
                "exportCount": meta["ExportCount"] if meta else 0,
                "importCount": meta["ImportCount"] if meta else 0,
                "total": (meta["ExportCount"] + meta["ImportCount"]) if meta else 0,
            },
        }


def round_or_none(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def build_summary(args):
    where, params = build_filters(args)
    with get_connection() as conn:
        kpi = conn.execute(
            f"""
            SELECT
                COUNT(*) AS shipments,
                COUNT(DISTINCT ShipmentID) AS shipmentIds,
                SUM(IsBosch) AS bosch,
                AVG(Volume) AS avgVolume,
                AVG(Weight) AS avgWeight,
                AVG(Chargeable) AS avgChargeable,
                AVG(Pieces) AS avgPieces,
                AVG(DimL) AS avgL,
                AVG(DimW) AS avgW,
                AVG(DimH) AS avgH
            FROM LclShipments
            {where}
            """,
            params,
        ).fetchone()
        months = conn.execute(
            f"""
            SELECT MonthName AS label, COUNT(*) AS count, AVG(Volume) AS avgVolume
            FROM LclShipments
            {where}
            GROUP BY MonthName
            """,
            params,
        ).fetchall()
        year_months = conn.execute(
            f"""
            SELECT Year AS year, MonthName AS month, COUNT(*) AS count
            FROM LclShipments
            {where}
            GROUP BY Year, MonthName
            """,
            params,
        ).fetchall()
        customers = conn.execute(
            f"""
            SELECT Customer AS label, COUNT(*) AS count
            FROM LclShipments
            {where} {'AND' if where else 'WHERE'} Customer != ''
            GROUP BY Customer
            ORDER BY count DESC
            LIMIT 10
            """,
            params,
        ).fetchall()
        month_counts = []
        for name in MONTH_ORDER:
            match = next((row for row in months if row["label"] == name), None)
            if match:
                month_counts.append({
                    "label": name,
                    "count": match["count"],
                    "avgVolume": round_or_none(match["avgVolume"], 3),
                })
        active_months = [item["count"] for item in month_counts if item["count"]]
        monthly_avg = round(sum(active_months) / len(active_months), 1) if active_months else 0
        shipments = kpi["shipments"] or 0
        bosch = kpi["bosch"] or 0
        years = sorted({str(row["year"]) for row in year_months if row["year"]}, reverse=False)
        by_year_month = []
        for year in years:
            values = []
            for name in MONTH_ORDER:
                match = next(
                    (row for row in year_months if str(row["year"]) == year and row["month"] == name),
                    None,
                )
                values.append(match["count"] if match else None)
            by_year_month.append({"year": year, "values": values})
        return {
            "kpis": {
                "shipments": shipments,
                "shipmentIds": kpi["shipmentIds"] or 0,
                "bosch": bosch,
                "boschShare": round((bosch / shipments) * 100, 1) if shipments else 0,
                "avgVolume": round_or_none(kpi["avgVolume"], 3),
                "avgWeight": round_or_none(kpi["avgWeight"], 1),
                "avgChargeable": round_or_none(kpi["avgChargeable"], 3),
                "avgPieces": round_or_none(kpi["avgPieces"], 2),
                "avgL": round_or_none(kpi["avgL"], 1),
                "avgW": round_or_none(kpi["avgW"], 1),
                "avgH": round_or_none(kpi["avgH"], 1),
                "monthlyAvgBills": monthly_avg,
            },
            "byMonth": month_counts,
            "byYearMonth": {
                "months": list(MONTH_ORDER),
                "years": by_year_month,
            },
            "byCustomer": [{"label": row["label"], "count": row["count"]} for row in customers],
        }


BRANCH_COORDS = {
    "SH1": (31.23, 121.47),
    "SZ1": (22.54, 114.06),
    "QDO": (36.07, 120.38),
    "NG1": (29.87, 121.55),
    "SIN": (1.35, 103.82),
}
CHINA_HUB = (31.23, 121.47)


def arrow_kind(direction):
    text = str(direction or "").lower()
    if "import" in text:
        return "import"
    if "export" in text:
        return "export"
    return "cross"


def hub_coords(args):
    branches = split_csv_param(args.get("branch"))
    if len(branches) == 1 and branches[0] in BRANCH_COORDS:
        return BRANCH_COORDS[branches[0]]
    return CHINA_HUB


def build_arrows(conn, where, params, hub):
    rows = conn.execute(
        f"""
        SELECT Direction AS direction, DestCtry AS iso2,
               MAX(CountryName) AS country, COUNT(ShipmentID) AS count
        FROM LclShipments
        {where} {'AND' if where else 'WHERE'} DestCtry != ''
        GROUP BY Direction, DestCtry
        ORDER BY count DESC
        LIMIT 40
        """,
        params,
    ).fetchall()
    hub_lat, hub_lng = hub
    arrows = []
    for row in rows:
        iso2 = str(row["iso2"] or "").upper()[:2]
        coords = COUNTRY_CENTROIDS.get(iso2)
        if not coords:
            continue
        dest_lat, dest_lng = coords
        kind = arrow_kind(row["direction"])
        if kind == "import":
            from_lat, from_lng, to_lat, to_lng = dest_lat, dest_lng, hub_lat, hub_lng
        else:
            from_lat, from_lng, to_lat, to_lng = hub_lat, hub_lng, dest_lat, dest_lng
        if abs(from_lat - to_lat) < 0.4 and abs(from_lng - to_lng) < 0.4:
            continue
        arrows.append({
            "iso2": iso2,
            "country": row["country"] or COUNTRY_NAMES.get(iso2, iso2),
            "direction": row["direction"] or "",
            "kind": kind,
            "count": row["count"],
            "fromLat": from_lat,
            "fromLng": from_lng,
            "toLat": to_lat,
            "toLng": to_lng,
        })
    return arrows


def build_map(args):
    where, params = build_filters(args)
    hub = hub_coords(args)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT DestCtry AS iso2, MAX(CountryName) AS country, COUNT(ShipmentID) AS count
            FROM LclShipments
            {where} {'AND' if where else 'WHERE'} DestCtry != ''
            GROUP BY DestCtry
            ORDER BY count DESC
            """,
            params,
        ).fetchall()
        arrows = build_arrows(conn, where, params, hub)
    points = []
    for row in rows:
        iso2 = str(row["iso2"] or "").upper()[:2]
        coords = COUNTRY_CENTROIDS.get(iso2)
        if not coords:
            continue
        lat, lng = coords
        points.append({
            "iso2": iso2,
            "country": row["country"] or COUNTRY_NAMES.get(iso2, iso2),
            "count": row["count"],
            "lat": lat,
            "lng": lng,
        })
    return {"points": points, "arrows": arrows}
