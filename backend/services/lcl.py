import re
import threading
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from io import BytesIO

from config import LCL_MAX_UPLOAD_MB
from db import ensure_lcl_shipment_id_unique, get_connection
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

RAW_SHEET_NAMES = {"raw", "rawdata", "raw data"}
KEEP_FIELDS_NORM = {
    re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip(): key for name, key in KEEP_FIELDS.items()
}
KEEP_FIELDS_COLLAPSED = {
    re.sub(r"[^a-z0-9]+", "", name.casefold()): key for name, key in KEEP_FIELDS.items()
}

MONTH_ORDER = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

_CACHE_LOCK = threading.Lock()
_FILTER_CACHE = None
_DASHBOARD_CACHE = {}
_DASHBOARD_CACHE_LIMIT = 40

DIM_RE = re.compile(
    r"^\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*$"
)


def local_tag(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def normalize_header(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().casefold()).strip()


def map_header(name):
    text = str(name or "").strip()
    if text in KEEP_FIELDS:
        return KEEP_FIELDS[text]
    mapped = KEEP_FIELDS_NORM.get(normalize_header(text))
    if mapped:
        return mapped
    return KEEP_FIELDS_COLLAPSED.get(re.sub(r"[^a-z0-9]+", "", text.casefold()))


def col_letters_to_index(ref):
    letters = []
    for ch in str(ref or ""):
        if ch.isalpha():
            letters.append(ch)
        else:
            break
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return max(n - 1, 0)


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
        key = map_header(field.get("name") if isinstance(field, dict) else field)
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


UPSERT_SQL = """
    INSERT INTO LclShipments (
        ShipmentID, Direction, Year, MonthName, YearMonth, JobBranch,
        DestCtry, CountryName, Customer, IsBosch, Weight, Volume,
        DimensionRaw, Pieces, DimL, DimW, DimH, Chargeable
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (ShipmentID) WHERE ShipmentID <> '' DO UPDATE SET
        Direction = EXCLUDED.Direction,
        Year = EXCLUDED.Year,
        MonthName = EXCLUDED.MonthName,
        YearMonth = EXCLUDED.YearMonth,
        JobBranch = EXCLUDED.JobBranch,
        DestCtry = EXCLUDED.DestCtry,
        CountryName = EXCLUDED.CountryName,
        Customer = EXCLUDED.Customer,
        IsBosch = EXCLUDED.IsBosch,
        Weight = EXCLUDED.Weight,
        Volume = EXCLUDED.Volume,
        DimensionRaw = EXCLUDED.DimensionRaw,
        Pieces = EXCLUDED.Pieces,
        DimL = EXCLUDED.DimL,
        DimW = EXCLUDED.DimW,
        DimH = EXCLUDED.DimH,
        Chargeable = EXCLUDED.Chargeable
"""


def empty_import_stats():
    return {"inserted": 0, "updated": 0, "skipped": 0}


def add_import_stats(stats, inserted=0, updated=0, skipped=0):
    stats["inserted"] += inserted
    stats["updated"] += updated
    stats["skipped"] += skipped
    return stats


def flush_rows(conn, buffer, stats=None):
    if stats is None:
        stats = empty_import_stats()
    if not buffer:
        return 0
    skipped = 0
    by_id = {}
    for row in buffer:
        shipment_id = to_text(row[0])
        if not shipment_id:
            skipped += 1
            continue
        by_id[shipment_id] = (shipment_id,) + tuple(row[1:])
    buffer.clear()
    rows = list(by_id.values())
    if not rows:
        add_import_stats(stats, skipped=skipped)
        return 0
    ids = [row[0] for row in rows]
    placeholders = ",".join("?" * len(ids))
    existing = {
        row[0]
        for row in conn.execute(
            f"SELECT ShipmentID FROM LclShipments WHERE ShipmentID IN ({placeholders})",
            ids,
        ).fetchall()
    }
    updated = sum(1 for shipment_id in ids if shipment_id in existing)
    inserted = len(ids) - updated
    conn.executemany(UPSERT_SQL, rows)
    conn.commit()
    add_import_stats(stats, inserted=inserted, updated=updated, skipped=skipped)
    return inserted + updated


def import_cache(zip_file, definition_name, records_name, direction, conn, stats):
    fields = parse_cache_fields(zip_file.read(definition_name))
    written = 0
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
                written += flush_rows(conn, buffer, stats)
                if written and written % 20000 == 0:
                    print(f"  {direction}: {written:,}", flush=True)
    written += flush_rows(conn, buffer, stats)
    return written


def find_raw_sheet_path(archive):
    try:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return None
    targets = {}
    for rel in rels:
        if local_tag(rel.tag) != "Relationship":
            continue
        targets[rel.get("Id")] = rel.get("Target")
    for sheet in workbook.iter():
        if local_tag(sheet.tag) != "sheet":
            continue
        name = normalize_header(sheet.get("name"))
        if name not in RAW_SHEET_NAMES:
            continue
        rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = targets.get(rid) or ""
        if not target:
            continue
        path = target.lstrip("/")
        if not path.startswith("xl/"):
            path = f"xl/{path}"
        return path
    return None


def load_shared_strings(archive):
    if "xl/sharedStrings.xml" not in set(archive.namelist()):
        return []
    strings = []
    with archive.open("xl/sharedStrings.xml") as handle:
        for _event, elem in ET.iterparse(handle, events=("end",)):
            if local_tag(elem.tag) != "si":
                continue
            parts = []
            for child in elem.iter():
                if local_tag(child.tag) == "t" and child.text:
                    parts.append(child.text)
            strings.append("".join(parts))
            elem.clear()
    return strings


def cell_value(elem, strings):
    kind = elem.get("t")
    if kind == "inlineStr":
        parts = []
        for child in elem.iter():
            if local_tag(child.tag) == "t" and child.text:
                parts.append(child.text)
        return "".join(parts)
    text = ""
    for child in list(elem):
        if local_tag(child.tag) == "v":
            text = child.text or ""
            break
    if kind == "s":
        try:
            return strings[int(text)]
        except (TypeError, ValueError, IndexError):
            return text
    if kind == "b":
        return 1 if str(text).strip().lower() in ("1", "true") else 0
    if kind == "n" or (kind in (None, "") and text):
        number = to_float(text)
        return number if number is not None else text
    return text


def import_raw_sheet(archive, sheet_path, conn, stats):
    strings = load_shared_strings(archive)
    col_map = {}
    header_done = False
    buffer = []
    export_count = 0
    import_count = 0
    with archive.open(sheet_path) as handle:
        for _event, elem in ET.iterparse(handle, events=("end",)):
            if local_tag(elem.tag) != "row":
                continue
            values = {}
            cursor = 0
            for cell in list(elem):
                if local_tag(cell.tag) != "c":
                    continue
                ref = cell.get("r")
                cursor = col_letters_to_index(ref) if ref else cursor
                values[cursor] = cell_value(cell, strings)
                cursor += 1
            if not header_done:
                for index, value in values.items():
                    key = map_header(value)
                    if key:
                        col_map[index] = key
                header_done = True
                elem.clear()
                if "shipment_id" not in col_map.values():
                    return None, "The Raw sheet is missing a ShipmentID column."
                if len(col_map) < 4:
                    return None, "The Raw sheet headers were not recognized. Use the Raw sheet from the LCL Volume workbook."
                continue
            raw = {key: values.get(index) for index, key in col_map.items()}
            if not any((raw.get("shipment_id"), raw.get("dest_ctry"), raw.get("customer"), raw.get("direction"))):
                elem.clear()
                continue
            row = slim_row(
                [{"name": name} for name in KEEP_FIELDS],
                [raw.get(KEEP_FIELDS[name]) for name in KEEP_FIELDS],
                to_text(raw.get("direction")),
            )
            if not to_text(row[0]):
                add_import_stats(stats, skipped=1)
                elem.clear()
                continue
            direction = to_text(row[1]).casefold()
            if direction == "import":
                import_count += 1
            else:
                export_count += 1
            buffer.append(row)
            elem.clear()
            if len(buffer) >= 2000:
                flush_rows(conn, buffer, stats)
    if not header_done:
        return None, "The Raw sheet is empty."
    flush_rows(conn, buffer, stats)
    return {"exportCount": export_count, "importCount": import_count}, None


def shipment_counts(conn):
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN Direction ILIKE 'import' THEN 1 ELSE 0 END), 0) AS import_count,
            COALESCE(SUM(CASE WHEN Direction NOT ILIKE 'import' THEN 1 ELSE 0 END), 0) AS export_count
        FROM LclShipments
        """
    ).fetchone()
    return {
        "total": int(row["total"] or 0),
        "importCount": int(row["import_count"] or 0),
        "exportCount": int(row["export_count"] or 0),
    }


def _refresh_lcl_meta(conn, filename, stamp):
    counts = shipment_counts(conn)
    conn.execute("DELETE FROM LclImportMeta")
    conn.execute(
        """
        INSERT INTO LclImportMeta (ID, Filename, ImportedAt, ExportCount, ImportCount)
        VALUES (1, ?, ?, ?, ?)
        """,
        (filename[:200], stamp, counts["exportCount"], counts["importCount"]),
    )
    conn.commit()
    return counts


def import_lcl_workbook(filename=None, data=None):
    if data is None:
        return None, "No file was uploaded."
    name = Path(str(filename or "lcl.xlsx")).name
    if not name.lower().endswith(".xlsx"):
        return None, "Please select the LCL .xlsx workbook."
    if not data:
        return None, "The uploaded file is empty."
    if len(data) > LCL_MAX_UPLOAD_MB * 1024 * 1024:
        return None, f"Upload exceeds the {LCL_MAX_UPLOAD_MB} MB limit."
    stamp = now_stamp()
    export_count = 0
    import_count = 0
    stats = empty_import_stats()
    stored = {"total": 0, "exportCount": 0, "importCount": 0}
    wrote = False
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        return None, "The file is not a valid Excel workbook."
    try:
        names = set(archive.namelist())
        raw_sheet = find_raw_sheet_path(archive)
        has_cache = "xl/pivotCache/pivotCacheDefinition1.xml" in names
        if not raw_sheet and not has_cache:
            return None, "This workbook has no Raw sheet or LCL pivot cache."
        with get_connection() as conn:
            ensure_lcl_shipment_id_unique(conn)
            try:
                used_raw = False
                if raw_sheet:
                    counts, error = import_raw_sheet(archive, raw_sheet, conn, stats)
                    wrote = (stats["inserted"] + stats["updated"]) > 0
                    if error and has_cache and not wrote:
                        stats = empty_import_stats()
                    elif error:
                        return None, error
                    else:
                        used_raw = True
                        export_count = counts["exportCount"]
                        import_count = counts["importCount"]
                if not used_raw and has_cache:
                    export_count = import_cache(
                        archive,
                        "xl/pivotCache/pivotCacheDefinition1.xml",
                        "xl/pivotCache/pivotCacheRecords1.xml",
                        "Export",
                        conn,
                        stats,
                    )
                    if "xl/pivotCache/pivotCacheDefinition2.xml" in names:
                        import_count = import_cache(
                            archive,
                            "xl/pivotCache/pivotCacheDefinition2.xml",
                            "xl/pivotCache/pivotCacheRecords2.xml",
                            "Import",
                            conn,
                            stats,
                        )
                    else:
                        import_count = 0
                    wrote = (stats["inserted"] + stats["updated"]) > 0
                if stats["inserted"] + stats["updated"] == 0:
                    return None, "No rows with a ShipmentID were imported."
                stored = _refresh_lcl_meta(conn, name, stamp)
                conn.execute("ANALYZE LclShipments")
            except Exception:
                if wrote or (stats["inserted"] + stats["updated"]) > 0:
                    clear_lcl_cache()
                raise
    finally:
        archive.close()
    clear_lcl_cache()
    return {
        "filename": name[:200],
        "importedAt": stamp,
        "exportCount": export_count,
        "importCount": import_count,
        "total": export_count + import_count,
        "inserted": stats["inserted"],
        "updated": stats["updated"],
        "skipped": stats["skipped"],
        "storedTotal": stored["total"],
    }, None


def split_csv_param(value):
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def clear_lcl_cache():
    global _FILTER_CACHE
    with _CACHE_LOCK:
        _FILTER_CACHE = None
        _DASHBOARD_CACHE.clear()


def _filter_key(args):
    def parts(name):
        return tuple(sorted(split_csv_param((args or {}).get(name))))

    return (
        parts("year"),
        parts("month"),
        parts("branch"),
        parts("direction"),
        parts("country"),
        parts("bosch"),
    )


def _store_dashboard(key, payload):
    with _CACHE_LOCK:
        if key in _DASHBOARD_CACHE:
            _DASHBOARD_CACHE.pop(key, None)
        elif len(_DASHBOARD_CACHE) >= _DASHBOARD_CACHE_LIMIT:
            _DASHBOARD_CACHE.pop(next(iter(_DASHBOARD_CACHE)))
        _DASHBOARD_CACHE[key] = payload


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
    bosch_vals = {part.strip().lower() for part in split_csv_param(args.get("bosch"))}
    yes = bool(bosch_vals & {"yes", "1", "true"})
    no = bool(bosch_vals & {"no", "0", "false"})
    if yes and not no:
        clauses.append("IsBosch=1")
    elif no and not yes:
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
    global _FILTER_CACHE
    with _CACHE_LOCK:
        if _FILTER_CACHE is not None:
            return _FILTER_CACHE
    with get_connection() as conn:
        months = distinct_values(conn, "MonthName")
        months.sort(key=lambda name: MONTH_ORDER.index(name) if name in MONTH_ORDER else 99)
        meta = conn.execute("SELECT * FROM LclImportMeta WHERE ID=1").fetchone()
        counts = shipment_counts(conn)
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
        data = {
            "years": distinct_values(conn, "Year"),
            "months": months,
            "branches": distinct_values(conn, "JobBranch"),
            "directions": distinct_values(conn, "Direction"),
            "countries": countries,
            "meta": {
                "filename": meta["Filename"] if meta else "",
                "importedAt": meta["ImportedAt"] if meta else "",
                "exportCount": counts["exportCount"],
                "importCount": counts["importCount"],
                "total": counts["total"],
            },
        }
    with _CACHE_LOCK:
        _FILTER_CACHE = data
    return data


def round_or_none(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def build_summary(args):
    where, params = build_filters(args)
    with get_connection() as conn:
        year_months = conn.execute(
            f"""
            SELECT Year AS year, MonthName AS month, COUNT(*) AS count,
                   SUM(IsBosch) AS bosch, SUM(Volume) AS volumeSum, COUNT(Volume) AS volumeN
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
    shipments = sum(row["count"] or 0 for row in year_months)
    bosch = sum(row["bosch"] or 0 for row in year_months)
    volume_sum = sum(row["volumeSum"] or 0 for row in year_months)
    volume_n = sum(row["volumeN"] or 0 for row in year_months)
    month_totals = {}
    for row in year_months:
        name = row["month"]
        if name:
            month_totals[name] = month_totals.get(name, 0) + (row["count"] or 0)
    month_counts = []
    for name in MONTH_ORDER:
        count = month_totals.get(name)
        if count:
            month_counts.append({"label": name, "count": count, "avgVolume": None})
    active_months = [item["count"] for item in month_counts if item["count"]]
    monthly_avg = round(sum(active_months) / len(active_months), 1) if active_months else 0
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
            "shipmentIds": shipments,
            "bosch": bosch,
            "boschShare": round((bosch / shipments) * 100, 1) if shipments else 0,
            "avgVolume": round_or_none(volume_sum / volume_n, 3) if volume_n else None,
            "avgWeight": None,
            "avgChargeable": None,
            "avgPieces": None,
            "avgL": None,
            "avgW": None,
            "avgH": None,
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


def build_map(args, include_arrows=True):
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
        arrows = build_arrows(conn, where, params, hub) if include_arrows else []
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


def build_dashboard(args):
    key = _filter_key(args)
    with _CACHE_LOCK:
        cached = _DASHBOARD_CACHE.get(key)
    if cached is not None:
        return cached
    include_arrows = bool(split_csv_param((args or {}).get("direction")))
    filters = list_filter_options()
    payload = {
        "filters": filters,
        "summary": build_summary(args),
        "map": build_map(args, include_arrows=include_arrows),
    }
    _store_dashboard(key, payload)
    return payload
