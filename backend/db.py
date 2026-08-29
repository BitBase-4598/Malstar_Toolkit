import sqlite3

from config import DB_PATH, SCHEMA_VERSION, UPLOAD_DIR
from util import letters_only


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _create_tables(conn):
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
    columns = {row[1] for row in conn.execute("PRAGMA table_info(CustomerRemarks)")}
    if "CustomerLetters" not in columns:
        conn.execute(
            "ALTER TABLE CustomerRemarks "
            "ADD COLUMN CustomerLetters TEXT NOT NULL DEFAULT ''"
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ActivityLogs (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Timestamp TEXT NOT NULL,
            Action TEXT NOT NULL,
            Detail TEXT NOT NULL DEFAULT '',
            ClientIP TEXT NOT NULL DEFAULT '',
            EventId TEXT NOT NULL DEFAULT '',
            RequestId TEXT NOT NULL DEFAULT '',
            Module TEXT NOT NULL DEFAULT '',
            ActionCode TEXT NOT NULL DEFAULT '',
            Outcome TEXT NOT NULL DEFAULT '',
            Severity TEXT NOT NULL DEFAULT '',
            ResourceType TEXT NOT NULL DEFAULT '',
            ResourceId TEXT NOT NULL DEFAULT '',
            Summary TEXT NOT NULL DEFAULT '',
            UserAgent TEXT NOT NULL DEFAULT ''
        )
    """)
    _ensure_activity_log_columns(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_logs_time ON ActivityLogs (Timestamp DESC, ID DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_logs_outcome "
        "ON ActivityLogs (Outcome, Timestamp DESC, ID DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_logs_module "
        "ON ActivityLogs (Module, Timestamp DESC, ID DESC)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ToolkitFiles (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            OriginalName TEXT NOT NULL,
            StoredName TEXT NOT NULL UNIQUE,
            Kind TEXT NOT NULL,
            Size INTEGER NOT NULL DEFAULT 0,
            UploadedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_toolkit_files_name ON ToolkitFiles (OriginalName)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Sops (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Title TEXT NOT NULL,
            Purpose TEXT NOT NULL DEFAULT '',
            Owner TEXT NOT NULL DEFAULT '',
            Revision TEXT NOT NULL DEFAULT '',
            Status TEXT NOT NULL DEFAULT 'draft',
            CreatedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sops_title ON Sops (Title)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS SopSteps (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            SopID INTEGER NOT NULL,
            StepNumber INTEGER NOT NULL,
            Instruction TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (SopID) REFERENCES Sops(ID) ON DELETE CASCADE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sop_steps_sop ON SopSteps (SopID, StepNumber)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS SopAttachments (
            SopID INTEGER NOT NULL,
            FileID INTEGER NOT NULL,
            PRIMARY KEY (SopID, FileID),
            FOREIGN KEY (SopID) REFERENCES Sops(ID) ON DELETE CASCADE,
            FOREIGN KEY (FileID) REFERENCES ToolkitFiles(ID)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS LeavePlans (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            LeaveDate TEXT NOT NULL,
            Person TEXT NOT NULL,
            LeaveType TEXT NOT NULL DEFAULT 'annual',
            Status TEXT NOT NULL DEFAULT 'planned',
            CreatedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL,
            UNIQUE (Person, LeaveDate)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leave_plans_date ON LeavePlans (LeaveDate)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS DashboardMeta (
            ID INTEGER PRIMARY KEY CHECK (ID = 1),
            Filename TEXT NOT NULL DEFAULT '',
            UploadedAt TEXT NOT NULL DEFAULT '',
            RowCount INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS DashboardBookings (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            OrderNumber TEXT NOT NULL DEFAULT '',
            ShipmentNumber TEXT NOT NULL DEFAULT '',
            MessageId TEXT NOT NULL DEFAULT '',
            ReportDate TEXT NOT NULL DEFAULT '',
            EmailReceived TEXT NOT NULL DEFAULT '',
            EmailStatus TEXT NOT NULL DEFAULT '',
            HandledBy TEXT NOT NULL DEFAULT '',
            HandlingTime TEXT NOT NULL DEFAULT '',
            BookingConvertedTime TEXT NOT NULL DEFAULT '',
            Subject TEXT NOT NULL DEFAULT '',
            Mailbox TEXT NOT NULL DEFAULT '',
            HandleWaitMinutes INTEGER,
            ProcessMinutes INTEGER
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dashboard_bookings_date ON DashboardBookings (ReportDate)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS RagChunks (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            SourceType TEXT NOT NULL,
            SourceID INTEGER NOT NULL,
            Title TEXT NOT NULL DEFAULT '',
            Locator TEXT NOT NULL DEFAULT '',
            Body TEXT NOT NULL DEFAULT '',
            UpdatedAt TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON RagChunks (SourceType, SourceID)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS RagIndexState (
            ID INTEGER PRIMARY KEY CHECK (ID = 1),
            LastIndexedAt TEXT NOT NULL DEFAULT '',
            ChunkCount INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Cases (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Status TEXT NOT NULL DEFAULT 'pending_review',
            StartTime TEXT NOT NULL DEFAULT '',
            CompletionTime TEXT NOT NULL DEFAULT '',
            Email TEXT NOT NULL DEFAULT '',
            Name TEXT NOT NULL DEFAULT '',
            HBL TEXT NOT NULL DEFAULT '',
            WronglyIdentified TEXT NOT NULL DEFAULT '',
            Incorrect TEXT NOT NULL DEFAULT '',
            Corrected TEXT NOT NULL DEFAULT '',
            CauseOfError TEXT NOT NULL DEFAULT '',
            ReceivedDate TEXT NOT NULL DEFAULT '',
            AdjustedHBL TEXT NOT NULL DEFAULT '',
            GscPic TEXT NOT NULL DEFAULT '',
            Week TEXT NOT NULL DEFAULT '',
            Date TEXT NOT NULL DEFAULT '',
            Category TEXT NOT NULL DEFAULT '',
            Description TEXT NOT NULL DEFAULT '',
            Action TEXT NOT NULL DEFAULT '',
            CreatedAt TEXT NOT NULL,
            UpdatedAt TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_status ON Cases (Status, UpdatedAt DESC, ID DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cases_hbl ON Cases (HBL)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS CaseFiles (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            CaseID INTEGER NOT NULL,
            OriginalName TEXT NOT NULL,
            StoredName TEXT NOT NULL UNIQUE,
            Kind TEXT NOT NULL,
            Size INTEGER NOT NULL DEFAULT 0,
            UploadedAt TEXT NOT NULL,
            FOREIGN KEY (CaseID) REFERENCES Cases(ID) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_case_files_case ON CaseFiles (CaseID, ID DESC)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS LclShipments (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            ShipmentID TEXT NOT NULL DEFAULT '',
            Direction TEXT NOT NULL DEFAULT '',
            Year TEXT NOT NULL DEFAULT '',
            MonthName TEXT NOT NULL DEFAULT '',
            YearMonth TEXT NOT NULL DEFAULT '',
            JobBranch TEXT NOT NULL DEFAULT '',
            DestCtry TEXT NOT NULL DEFAULT '',
            CountryName TEXT NOT NULL DEFAULT '',
            Customer TEXT NOT NULL DEFAULT '',
            IsBosch INTEGER NOT NULL DEFAULT 0,
            Weight REAL,
            Volume REAL,
            DimensionRaw TEXT NOT NULL DEFAULT '',
            Pieces REAL,
            DimL REAL,
            DimW REAL,
            DimH REAL,
            Chargeable REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lcl_year ON LclShipments (Year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lcl_month ON LclShipments (MonthName)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lcl_branch ON LclShipments (JobBranch)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lcl_direction ON LclShipments (Direction)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lcl_dest ON LclShipments (DestCtry)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lcl_bosch ON LclShipments (IsBosch)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS LclImportMeta (
            ID INTEGER PRIMARY KEY CHECK (ID = 1),
            Filename TEXT NOT NULL DEFAULT '',
            ImportedAt TEXT NOT NULL DEFAULT '',
            ExportCount INTEGER NOT NULL DEFAULT 0,
            ImportCount INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS SchemaVersion (
            ID INTEGER PRIMARY KEY CHECK (ID = 1),
            Version INTEGER NOT NULL
        )
    """)
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS RagChunksFts USING fts5(
                Title,
                Locator,
                Body,
                content='RagChunks',
                content_rowid='ID',
                tokenize='porter unicode61'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS rag_chunks_ai AFTER INSERT ON RagChunks BEGIN
                INSERT INTO RagChunksFts(rowid, Title, Locator, Body)
                VALUES (new.ID, new.Title, new.Locator, new.Body);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS rag_chunks_ad AFTER DELETE ON RagChunks BEGIN
                INSERT INTO RagChunksFts(RagChunksFts, rowid, Title, Locator, Body)
                VALUES ('delete', old.ID, old.Title, old.Locator, old.Body);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS rag_chunks_au AFTER UPDATE ON RagChunks BEGIN
                INSERT INTO RagChunksFts(RagChunksFts, rowid, Title, Locator, Body)
                VALUES ('delete', old.ID, old.Title, old.Locator, old.Body);
                INSERT INTO RagChunksFts(rowid, Title, Locator, Body)
                VALUES (new.ID, new.Title, new.Locator, new.Body);
            END
        """)
    except sqlite3.OperationalError:
        pass


def _ensure_activity_log_columns(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(ActivityLogs)")}
    additions = (
        ("EventId", "TEXT NOT NULL DEFAULT ''"),
        ("RequestId", "TEXT NOT NULL DEFAULT ''"),
        ("Module", "TEXT NOT NULL DEFAULT ''"),
        ("ActionCode", "TEXT NOT NULL DEFAULT ''"),
        ("Outcome", "TEXT NOT NULL DEFAULT ''"),
        ("Severity", "TEXT NOT NULL DEFAULT ''"),
        ("ResourceType", "TEXT NOT NULL DEFAULT ''"),
        ("ResourceId", "TEXT NOT NULL DEFAULT ''"),
        ("Summary", "TEXT NOT NULL DEFAULT ''"),
        ("UserAgent", "TEXT NOT NULL DEFAULT ''"),
    )
    for name, definition in additions:
        if name not in columns:
            conn.execute(f"ALTER TABLE ActivityLogs ADD COLUMN {name} {definition}")


def _backfill_activity_logs(conn):
    conn.execute(
        """
        UPDATE ActivityLogs
        SET Outcome='failure', Severity='warning'
        WHERE Outcome='' AND lower(Action) LIKE '%fail%'
        """
    )
    conn.execute(
        """
        UPDATE ActivityLogs
        SET Outcome='success', Severity='info'
        WHERE Outcome=''
        """
    )
    conn.execute(
        """
        UPDATE ActivityLogs
        SET Summary=Detail
        WHERE Summary='' AND Detail!=''
        """
    )


def _schema_version(conn):
    row = conn.execute("SELECT Version FROM SchemaVersion WHERE ID=1").fetchone()
    return row["Version"] if row else 0


def _set_schema_version(conn, version):
    conn.execute(
        """
        INSERT INTO SchemaVersion (ID, Version) VALUES (1, ?)
        ON CONFLICT(ID) DO UPDATE SET Version=excluded.Version
        """,
        (version,),
    )


def _run_once_side_effects(conn):
    for row in conn.execute("SELECT ID, Customer FROM CustomerRemarks"):
        conn.execute(
            "UPDATE CustomerRemarks SET CustomerLetters=? WHERE ID=?",
            (letters_only(row["Customer"]), row["ID"]),
        )
    conn.execute(
        """
        DELETE FROM ActivityLogs
        WHERE lower(Action) IN (
            'opened malstar_toolkit',
            'opened add form',
            'opened edit form',
            'opened section',
            'copied cell',
            'copy failed',
            'delete cancelled',
            'csv import started',
            'search',
            'list records',
            'ui event',
            'malstar_toolkit started',
            'file preview failed'
        )
        OR Action LIKE 'Opened %'
        OR Action LIKE 'Copied %'
        OR Action LIKE 'GET %'
        OR Action LIKE 'POST %'
        OR Action LIKE 'PUT %'
        OR Action LIKE 'PATCH %'
        OR Action LIKE 'DELETE %'
        """
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


def migrate():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        _create_tables(conn)
        current = _schema_version(conn)
        if current < 1:
            _run_once_side_effects(conn)
            _set_schema_version(conn, 1)
        if current < 2:
            _ensure_activity_log_columns(conn)
            _backfill_activity_logs(conn)
            _set_schema_version(conn, 2)
        if current < 3:
            _set_schema_version(conn, 3)
        if current < 4:
            _set_schema_version(conn, 4)
        if current < SCHEMA_VERSION:
            _set_schema_version(conn, SCHEMA_VERSION)
