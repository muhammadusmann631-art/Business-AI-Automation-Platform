"""Phase 4 — real database layer (SQLite).

A genuine on-disk relational database. All reads go through a connection
opened in read-only mode (``mode=ro``) AND a SELECT-only validator, so the
SQL tool physically cannot write. Kept separate from the agent code so the
backing store can be swapped for Postgres later without touching main.py.

Safety rules enforced here (Phase 4):
- read-only: SELECT statements only, single statement, no DML/DDL keywords.
- parameterised: callers pass values via ``params``, never string-concatenated.
- credentials/location come from backend/.env (DATABASE_PATH), never hard-coded.
"""

import os
import re
import sqlite3
from pathlib import Path

_DEFAULT_PATH = Path(__file__).parent / "company.db"


def _db_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if not configured:
        return _DEFAULT_PATH
    path = Path(configured)
    # Relative paths resolve against the backend dir, not the process CWD.
    return path if path.is_absolute() else Path(__file__).parent / path


# Statements that must never run through the read-only tool.
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|"
    r"PRAGMA|ATTACH|DETACH|VACUUM|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    """Raised when a query is not a safe, single read-only SELECT."""


def _ensure_read_only(sql: str) -> None:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise UnsafeQueryError("Empty query.")
    if ";" in stripped:
        raise UnsafeQueryError("Multiple statements are not allowed.")
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise UnsafeQueryError("Only SELECT queries are allowed (read-only).")
    if _FORBIDDEN.search(stripped):
        raise UnsafeQueryError("Query contains a forbidden write/DDL keyword.")


def run_select(sql: str, params: tuple = ()) -> list[dict]:
    """Run a validated, parameterised SELECT against the read-only connection."""
    _ensure_read_only(sql)
    # mode=ro: SQLite itself rejects any write, a second line of defence.
    uri = f"file:{_db_path().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_sales(month: str) -> list[dict]:
    """Parameterised read-only lookup of sales for a month."""
    return run_select(
        "SELECT month, amount FROM sales WHERE month = ? COLLATE NOCASE",
        (month.strip(),),
    )


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


# --------------------------------------------------------------------------- #
# Schema — the full business database (Level 1)
# --------------------------------------------------------------------------- #
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    month TEXT PRIMARY KEY,
    amount INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    company TEXT,
    phone TEXT,
    city TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    due_date DATE,
    paid_date DATE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def seed() -> None:
    """Create and populate ALL business tables. Idempotent; safe to re-run.

    Uses a normal read-write connection — this is setup, NOT the tool path.
    """
    path = _db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        # Migrate the original sales table to link to customers.
        if not _column_exists(conn, "sales", "customer_id"):
            conn.execute("ALTER TABLE sales ADD COLUMN customer_id INTEGER")

        _seed_sales(conn)
        _seed_customers(conn)
        _seed_products(conn)
        _seed_invoices(conn)
        _seed_expenses(conn)
        conn.commit()

        counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("sales", "customers", "invoices", "products", "expenses")
        }
        print(f"[DB] seeded {path.name}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    finally:
        conn.close()


def _seed_sales(conn: sqlite3.Connection) -> None:
    rows = [
        ("January", 12000, 1), ("February", 15500, 3), ("March", 18750, 5),
        ("April", 21000, 2), ("May", 26300, 7), ("June", 45000, 4),
        ("July", 39800, 6), ("August", 41200, 8), ("September", 33400, 9),
        ("October", 29900, 10), ("November", 47600, 2), ("December", 38000, 4),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO sales (month, amount, customer_id) VALUES (?, ?, ?)", rows
    )


def _seed_customers(conn: sqlite3.Connection) -> None:
    rows = [
        (1, "Ahmed Raza", "ahmed@techsol.pk", "TechSol Pvt Ltd", "+92-300-1234567", "Karachi", "active"),
        (2, "Fatima Khan", "fatima@nexawave.com", "NexaWave", "+92-321-2345678", "Lahore", "active"),
        (3, "Bilal Sheikh", "bilal@dubaitrade.ae", "Dubai Trade Co", "+971-50-3456789", "Dubai", "active"),
        (4, "Sara Ali", "sara@londonsoft.co.uk", "London Software", "+44-20-45678901", "London", "active"),
        (5, "Usman Malik", "usman@zentech.pk", "ZenTech", "+92-333-5678901", "Islamabad", "lead"),
        (6, "Ayesha Iqbal", "ayesha@brightmedia.com", "Bright Media", "+92-301-6789012", "Karachi", "active"),
        (7, "Hamza Tariq", "hamza@falconlogistics.ae", "Falcon Logistics", "+971-55-7890123", "Dubai", "inactive"),
        (8, "Zainab Hassan", "zainab@corevision.com", "CoreVision", "+92-345-8901234", "Lahore", "active"),
        (9, "Omar Farooq", "omar@peakfinance.co.uk", "Peak Finance", "+44-16-90123456", "London", "active"),
        (10, "Hina Javed", "hina@lushmart.pk", "LushMart", "+92-311-0123456", "Faisalabad", "active"),
        (11, "Kamran Akmal", "kamran@swifttrans.pk", "Swift Transport", "+92-302-1112223", "Karachi", "lead"),
        (12, "Nadia Sultan", "nadia@velvetco.com", "Velvet Co", "+92-322-2223334", "Lahore", "inactive"),
        (13, "Imran Butt", "imran@apextech.ae", "Apex Tech", "+971-52-3334445", "Dubai", "active"),
        (14, "Rabia Noor", "rabia@cloudnine.co.uk", "Cloud Nine", "+44-11-44445556", "Manchester", "active"),
        (15, "Tariq Mehmood", "tariq@greenfields.pk", "Green Fields", "+92-300-5556667", "Multan", "active"),
        (16, "Sana Mir", "sana@bluewave.com", "BlueWave", "+92-321-6667778", "Karachi", "lead"),
        (17, "Faisal Qureshi", "faisal@orbitsys.ae", "Orbit Systems", "+971-56-7778889", "Abu Dhabi", "active"),
        (18, "Maria Yousuf", "maria@pinnacle.co.uk", "Pinnacle Ltd", "+44-13-88889990", "Birmingham", "inactive"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO customers (id, name, email, company, phone, city, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)", rows
    )


def _seed_products(conn: sqlite3.Connection) -> None:
    rows = [
        (1, "AGI-CORE License (Annual)", "Software License", 12000.0, 100, "active"),
        (2, "AGI-CORE License (Monthly)", "Software License", 1200.0, 250, "active"),
        (3, "Business Analytics Consulting", "Consulting", 8500.0, 0, "active"),
        (4, "Data Migration Service", "Service", 5000.0, 0, "active"),
        (5, "Enterprise Server Rack", "Hardware", 22000.0, 12, "active"),
        (6, "Cloud Storage Add-on", "Software License", 300.0, 500, "active"),
        (7, "AI Training Workshop", "Training", 3500.0, 40, "active"),
        (8, "Custom Integration", "Service", 15000.0, 0, "active"),
        (9, "Support Plan (Premium)", "Service", 2000.0, 0, "active"),
        (10, "Legacy Analytics Tool", "Software License", 900.0, 5, "discontinued"),
        (11, "Networking Switch Pro", "Hardware", 4500.0, 30, "active"),
        (12, "Security Audit Package", "Consulting", 9800.0, 0, "active"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO products (id, name, category, price, stock, status) "
        "VALUES (?, ?, ?, ?, ?, ?)", rows
    )


def _seed_invoices(conn: sqlite3.Connection) -> None:
    # (id, invoice_number, customer_id, amount, status, due_date, paid_date, description)
    rows = [
        (1, "INV-2026-001", 1, 12000.0, "paid", "2026-01-15", "2026-01-10", "Annual license renewal"),
        (2, "INV-2026-002", 2, 8500.0, "paid", "2026-01-20", "2026-01-18", "Analytics consulting"),
        (3, "INV-2026-003", 3, 22000.0, "pending", "2026-07-30", None, "Server rack order"),
        (4, "INV-2026-004", 4, 5000.0, "overdue", "2026-05-01", None, "Data migration"),
        (5, "INV-2026-005", 6, 3500.0, "paid", "2026-02-10", "2026-02-09", "AI workshop"),
        (6, "INV-2026-006", 8, 15000.0, "pending", "2026-08-05", None, "Custom integration"),
        (7, "INV-2026-007", 9, 2000.0, "paid", "2026-02-28", "2026-02-25", "Premium support"),
        (8, "INV-2026-008", 10, 1200.0, "overdue", "2026-04-15", None, "Monthly license"),
        (9, "INV-2026-009", 1, 9800.0, "pending", "2026-07-20", None, "Security audit"),
        (10, "INV-2026-010", 13, 4500.0, "paid", "2026-03-12", "2026-03-11", "Networking switch"),
        (11, "INV-2026-011", 2, 12000.0, "paid", "2026-03-25", "2026-03-20", "License renewal"),
        (12, "INV-2026-012", 15, 5000.0, "pending", "2026-07-28", None, "Data migration"),
        (13, "INV-2026-013", 6, 8500.0, "overdue", "2026-05-10", None, "Consulting"),
        (14, "INV-2026-014", 17, 22000.0, "pending", "2026-08-15", None, "Server rack"),
        (15, "INV-2026-015", 4, 15000.0, "paid", "2026-04-05", "2026-04-01", "Integration"),
        (16, "INV-2026-016", 8, 3500.0, "paid", "2026-04-18", "2026-04-15", "Training"),
        (17, "INV-2026-017", 9, 9800.0, "pending", "2026-07-25", None, "Security audit"),
        (18, "INV-2026-018", 13, 2000.0, "overdue", "2026-05-20", None, "Support plan"),
        (19, "INV-2026-019", 1, 1200.0, "paid", "2026-05-28", "2026-05-26", "Monthly license"),
        (20, "INV-2026-020", 15, 12000.0, "pending", "2026-08-01", None, "Annual license"),
        (21, "INV-2026-021", 2, 4500.0, "paid", "2026-06-08", "2026-06-05", "Networking"),
        (22, "INV-2026-022", 17, 8500.0, "pending", "2026-07-18", None, "Consulting"),
        (23, "INV-2026-023", 6, 15000.0, "overdue", "2026-06-01", None, "Integration"),
        (24, "INV-2026-024", 3, 22000.0, "paid", "2026-06-15", "2026-06-12", "Hardware order"),
        (25, "INV-2026-025", 10, 3500.0, "pending", "2026-07-22", None, "Workshop"),
        (26, "INV-2026-026", 4, 500.0, "paid", "2026-06-20", "2026-06-19", "Cloud add-on"),
        (27, "INV-2026-027", 8, 9800.0, "pending", "2026-08-10", None, "Security audit"),
        (28, "INV-2026-028", 9, 2000.0, "cancelled", "2026-05-30", None, "Cancelled support"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO invoices "
        "(id, invoice_number, customer_id, amount, status, due_date, paid_date, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
    )


def _seed_expenses(conn: sqlite3.Connection) -> None:
    rows = [
        (1, "salary", 45000.0, "January payroll", "2026-01-31"),
        (2, "rent", 8000.0, "Office rent Jan", "2026-01-05"),
        (3, "utilities", 1200.0, "Electricity + internet", "2026-01-10"),
        (4, "marketing", 5000.0, "Google Ads campaign", "2026-01-15"),
        (5, "supplies", 800.0, "Office supplies", "2026-01-20"),
        (6, "salary", 45000.0, "February payroll", "2026-02-28"),
        (7, "rent", 8000.0, "Office rent Feb", "2026-02-05"),
        (8, "marketing", 6500.0, "LinkedIn campaign", "2026-02-14"),
        (9, "utilities", 1100.0, "Utilities Feb", "2026-02-10"),
        (10, "salary", 47000.0, "March payroll", "2026-03-31"),
        (11, "rent", 8000.0, "Office rent Mar", "2026-03-05"),
        (12, "supplies", 1500.0, "New monitors", "2026-03-18"),
        (13, "marketing", 4200.0, "Content marketing", "2026-03-22"),
        (14, "salary", 47000.0, "April payroll", "2026-04-30"),
        (15, "rent", 8000.0, "Office rent Apr", "2026-04-05"),
        (16, "utilities", 1300.0, "Utilities Apr", "2026-04-10"),
        (17, "marketing", 7000.0, "Trade show booth", "2026-04-25"),
        (18, "salary", 48000.0, "May payroll", "2026-05-31"),
        (19, "rent", 8000.0, "Office rent May", "2026-05-05"),
        (20, "supplies", 950.0, "Stationery + coffee", "2026-05-15"),
        (21, "marketing", 5500.0, "Email campaign tool", "2026-05-20"),
        (22, "salary", 48000.0, "June payroll", "2026-06-30"),
        (23, "rent", 8000.0, "Office rent Jun", "2026-06-05"),
        (24, "utilities", 1250.0, "Utilities Jun", "2026-06-10"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO expenses (id, category, amount, description, date) "
        "VALUES (?, ?, ?, ?, ?)", rows
    )


# --------------------------------------------------------------------------- #
# Admin CRUD — WRITE access for the human admin only (NOT the agent's tool).
# The agent SQL path stays strictly read-only; this parallel path is how the
# /admin panel manages data. Auth should protect these in production.
# --------------------------------------------------------------------------- #
ADMIN_TABLES: dict[str, list[str]] = {
    "customers": ["name", "email", "company", "phone", "city", "status"],
    "invoices": ["invoice_number", "customer_id", "amount", "status",
                 "due_date", "paid_date", "description"],
    "products": ["name", "category", "price", "stock", "status"],
    "expenses": ["category", "amount", "description", "date"],
    "sales": ["month", "amount", "customer_id"],
}
_ADMIN_KEY = {"sales": "month"}  # everything else keys on "id"


def _admin_key(table: str) -> str:
    return _ADMIN_KEY.get(table, "id")


def _check_table(table: str) -> None:
    if table not in ADMIN_TABLES:
        raise UnsafeQueryError(f"Unknown table: {table}")


def admin_list(table: str) -> list[dict]:
    _check_table(table)
    conn = sqlite3.connect(_db_path())
    try:
        conn.row_factory = sqlite3.Row
        order = _admin_key(table)
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def admin_insert(table: str, data: dict) -> dict:
    _check_table(table)
    cols = [c for c in ADMIN_TABLES[table] if c in data]
    if not cols:
        raise UnsafeQueryError("No valid columns provided.")
    placeholders = ", ".join("?" for _ in cols)
    conn = sqlite3.connect(_db_path())
    try:
        cur = conn.execute(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(data[c] for c in cols),
        )
        conn.commit()
        key = _admin_key(table)
        new_id = data[key] if table == "sales" else cur.lastrowid
        return {"ok": True, "id": new_id}
    finally:
        conn.close()


def admin_update(table: str, row_id, data: dict) -> dict:
    _check_table(table)
    cols = [c for c in ADMIN_TABLES[table] if c in data]
    if not cols:
        raise UnsafeQueryError("No valid columns provided.")
    assignments = ", ".join(f"{c}=?" for c in cols)
    conn = sqlite3.connect(_db_path())
    try:
        cur = conn.execute(
            f"UPDATE {table} SET {assignments} WHERE {_admin_key(table)}=?",
            tuple(data[c] for c in cols) + (row_id,),
        )
        conn.commit()
        return {"ok": True, "updated": cur.rowcount}
    finally:
        conn.close()


def admin_delete(table: str, row_id) -> dict:
    _check_table(table)
    conn = sqlite3.connect(_db_path())
    try:
        cur = conn.execute(f"DELETE FROM {table} WHERE {_admin_key(table)}=?", (row_id,))
        conn.commit()
        return {"ok": True, "deleted": cur.rowcount}
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
