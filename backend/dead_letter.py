"""Phase 6 — dead-letter store + operator alert.

When a tool fails even after all retries, the task must NOT be silently lost.
We append it to a small JSON file on disk (``dead_letters.json``) so it can be
investigated or replayed later, and we raise a visible alert (terminal log +
an ``alerts.json`` record).

Deliberately lightweight for Phase 6 — a JSON file, not RabbitMQ/Redis/Celery.
The interface (``save`` / ``alert``) is small so it can be swapped for a real
queue later without touching callers.
"""

import json
from datetime import datetime
from pathlib import Path

DEAD_LETTER_PATH = Path(__file__).parent / "dead_letters.json"
ALERTS_PATH = Path(__file__).parent / "alerts.json"


def _log(msg: str) -> None:
    """print() that can't crash on a console with a limited codec (e.g. cp1252
    can't encode the ⚠️ emoji). Falls back to an ASCII-safe rendering."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


def _append(path: Path, entry: dict) -> None:
    """Append one entry to a JSON array file, tolerating a missing/corrupt file."""
    data: list = []
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "[]")
            if not isinstance(data, list):
                data = []
        except json.JSONDecodeError:
            data = []  # corrupt file: start fresh rather than crash
    data.append(entry)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def alert(tool: str, attempts: int, request: str = "", session_id: str = "") -> str:
    """Raise a visible operator alert. Returns the alert message.

    Phase 6 alert = a clear terminal log + a persistent record. No Slack/email
    /SMS integration yet (later enhancement).
    """
    message = (
        f"[ALERT] ⚠️ TOOL FAILURE — {tool} failed after {attempts} attempts. "
        f"Task saved to dead-letter store. Manual review required."
    )
    _log(message)
    _append(
        ALERTS_PATH,
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "tool": tool,
            "attempts": attempts,
            "request": request,
            "session_id": session_id,
            "message": message,
        },
    )
    return message


def save(
    request: str,
    tool: str,
    error,
    attempts: int,
    session_id: str,
    step: str | None = None,
) -> dict:
    """Persist a failed task to the dead-letter store and fire the alert.

    Each entry carries everything needed to investigate or replay later:
    timestamp, the original request, which tool/step failed, the error, how
    many attempts were made, and the session id (from Phase 3 memory).
    """
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "request": request,
        "tool": tool,
        "step": step,
        "error": str(error),
        "attempts": attempts,
        "session_id": session_id,
    }
    _append(DEAD_LETTER_PATH, entry)
    _log(f"[DEAD-LETTER] task saved — tool: {tool}, error: {error}, attempts: {attempts}")
    alert(tool, attempts, request=request, session_id=session_id)
    return entry


if __name__ == "__main__":
    e = save(
        request="email June sales report to client",
        tool="generate_report",
        error="disk full",
        attempts=4,
        session_id="demo-session",
        step="generate the PDF report",
    )
    print("saved entry:", e)
    print("dead-letter file:", DEAD_LETTER_PATH)
