import csv
import io
import os
import sqlite3
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(
    os.environ.get("DATABASE_PATH", BASE_DIR / "customer_remark.db")
).expanduser()
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "5"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]


def resolve_static_dir():
    env_path = os.environ.get("STATIC_DIR")
    if env_path:
        return Path(env_path)
    candidates = [
        BASE_DIR / "frontend" / "dist",
        BASE_DIR.parent / "frontend" / "dist",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


STATIC_DIR = resolve_static_dir()

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
if CORS_ORIGINS:
    CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})


def letters_only(value):
    return "".join(ch for ch in (value or "") if ch.isalpha()).casefold()


def record_values(payload):
    return (
        payload["ctrlOrgcode"],
        payload["customer"],
        payload["customerLetters"],
        payload["remark1"],
        payload["remark2"],
        payload["remark3"],
    )


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS CustomerRemarks (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CTRLOrgcode TEXT NOT NULL,
                Customer TEXT NOT NULL,
                CustomerLetters TEXT NOT NULL DEFAULT '',
                Remark1 TEXT NOT NULL DEFAULT '',
                Remark2 TEXT NOT NULL DEFAULT '',
                Remark3 TEXT NOT NULL DEFAULT '',
                CreateTime TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UpdateTime TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (CTRLOrgcode, Customer)
            )
        """)
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(CustomerRemarks)")
        }
        if "CustomerLetters" not in columns:
            conn.execute(
                "ALTER TABLE CustomerRemarks "
                "ADD COLUMN CustomerLetters TEXT NOT NULL DEFAULT ''"
            )
        for row in conn.execute("SELECT ID, Customer FROM CustomerRemarks"):
            conn.execute(
                "UPDATE CustomerRemarks SET CustomerLetters=? WHERE ID=?",
                (letters_only(row["Customer"]), row["ID"]),
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_remarks_orgcode "
            "ON CustomerRemarks (CTRLOrgcode)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_remarks_customer "
            "ON CustomerRemarks (Customer)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer_remarks_letters "
            "ON CustomerRemarks (CustomerLetters)"
        )
        count = conn.execute("SELECT COUNT(*) FROM CustomerRemarks").fetchone()[0]
        if count == 0:
            seeds = [
                ("CQN", "Demo Customer A", "Priority customer", "Weekly review", "Active"),
                ("SHA", "Demo Customer B", "Standard process", "", "Active"),
                ("HKG", "Demo Customer C", "Check instruction", "Confirm before release", ""),
            ]
            conn.executemany(
                """
                INSERT INTO CustomerRemarks
                    (CTRLOrgcode, Customer, CustomerLetters, Remark1, Remark2, Remark3)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (org, customer, letters_only(customer), remark1, remark2, remark3)
                    for org, customer, remark1, remark2, remark3 in seeds
                ],
            )


init_db()


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


@app.get("/api/health")
def health():
    return jsonify({"success": True, "message": "Customer Remark API is running"})


@app.get("/api/customer-remarks")
def list_records():
    q_letters = letters_only(request.args.get("q", ""))
    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("pageSize", 20, type=int), 1), 100)
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


@app.post("/api/customer-remarks")
def create_record():
    payload, error = parse_payload(request.get_json(silent=True) or {})
    if error:
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
        return jsonify({
            "success": False,
            "message": "The CTRLOrgcode and Customer combination already exists.",
        }), 409
    return jsonify({"success": True, "message": "Record created", "data": row_to_dict(row)}), 201


@app.put("/api/customer-remarks/<int:record_id>")
def update_record(record_id):
    payload, error = parse_payload(request.get_json(silent=True) or {})
    if error:
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
                return jsonify({"success": False, "message": "Record not found"}), 404
            row = conn.execute(
                "SELECT * FROM CustomerRemarks WHERE ID=?", (record_id,)
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({
            "success": False,
            "message": "The CTRLOrgcode and Customer combination already exists.",
        }), 409
    return jsonify({"success": True, "message": "Record updated", "data": row_to_dict(row)})


@app.delete("/api/customer-remarks/<int:record_id>")
def delete_record(record_id):
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM CustomerRemarks WHERE ID=?", (record_id,))
    if cur.rowcount == 0:
        return jsonify({"success": False, "message": "Record not found"}), 404
    return jsonify({"success": True, "message": "Record deleted"})


@app.post("/api/customer-remarks/import-csv")
def import_csv():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No CSV file was uploaded."}), 400
    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".csv"):
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

        records, errors, seen = [], [], set()

        def value(row, name):
            original = headers.get(name.lower())
            return row.get(original, "") if original else ""

        for row_no, row in enumerate(reader, start=2):
            if not any(str(v or "").strip() for v in row.values()):
                continue
            payload, error = parse_payload({
                "ctrlOrgcode": value(row, "ctrlorgcode"),
                "customer": value(row, "customer"),
                "remark1": value(row, "remark1"),
                "remark2": value(row, "remark2"),
                "remark3": value(row, "remark3"),
            })
            if error:
                errors.append({"row": row_no, "message": error})
                continue
            key = (payload["ctrlOrgcode"].casefold(), payload["customer"].casefold())
            if key in seen:
                errors.append({
                    "row": row_no,
                    "message": "Duplicate CTRLOrgcode and Customer in CSV.",
                })
                continue
            seen.add(key)
            records.append(payload)

        if errors:
            return jsonify({
                "success": False,
                "message": "CSV validation failed. Nothing was imported.",
                "errors": errors[:100],
            }), 400
        if not records:
            return jsonify({"success": False, "message": "CSV contains no data rows."}), 400

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
        return jsonify({
            "success": True,
            "message": "CSV import completed",
            "processed": len(records),
            "created": created,
            "updated": updated,
        })
    except UnicodeDecodeError:
        return jsonify({
            "success": False,
            "message": "Please save the CSV with UTF-8 encoding.",
        }), 400
    except csv.Error as error:
        return jsonify({"success": False, "message": f"Invalid CSV: {error}"}), 400


@app.errorhandler(413)
def too_large(_):
    return jsonify({
        "success": False,
        "message": f"CSV file exceeds the {MAX_UPLOAD_MB} MB limit.",
    }), 413


@app.get("/")
def index():
    if not (STATIC_DIR / "index.html").is_file():
        return jsonify({
            "success": True,
            "message": "Customer Remark API is running. Frontend build not found.",
        })
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/<path:asset_path>")
def spa_or_static(asset_path):
    if asset_path.startswith("api/"):
        abort(404)
    target = STATIC_DIR / asset_path
    if target.is_file():
        return send_from_directory(STATIC_DIR, asset_path)
    if (STATIC_DIR / "index.html").is_file():
        return send_from_directory(STATIC_DIR, "index.html")
    abort(404)


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", "5000")))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    app.run(host=host, port=port, debug=debug)
