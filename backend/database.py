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


def seed() -> None:
    """Create and populate the sales table. Idempotent; safe to re-run.

    Uses a normal read-write connection — this is setup, NOT the tool path.
    """
    path = _db_path()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sales ("
            "  month TEXT PRIMARY KEY,"
            "  amount INTEGER NOT NULL"
            ")"
        )
        rows = [
            ("January", 12000),
            ("February", 15500),
            ("March", 18750),
            ("April", 21000),
            ("May", 26300),
            ("June", 45000),
            ("July", 39800),
            ("August", 41200),
            ("September", 33400),
            ("October", 29900),
            ("November", 47600),
            ("December", 38000),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO sales (month, amount) VALUES (?, ?)", rows
        )
        conn.commit()
        print(f"[DB] seeded {len(rows)} rows into {path.name}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
