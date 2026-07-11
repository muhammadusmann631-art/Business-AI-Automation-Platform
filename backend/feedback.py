"""Phase 10 — feedback loop: store, categorize, analyze, and apply.

Closes the loop. When a user rates a response (👍/👎) or corrects it, the
feedback is stored (linked to the Phase 9 trace_id), auto-categorized with
deterministic keyword rules (NO LLM), and made available to three application
mechanisms driven from main.py:

  A. preference auto-extraction  — format corrections become Phase 3 prefs.
  B. context injection           — relevant past corrections are fed into the
                                   Supervisor context for similar new requests.
  C. recurring-issue flagging    — 3+ negatives of one category raise a flag.

Storage is a small SQLite file (feedback.db). Every public function swallows
its own errors so feedback handling can never crash a chat request.
"""

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB = Path(__file__).parent / "feedback.db"

RECURRING_THRESHOLD = 3  # 3+ negatives of one category -> flag it

# Deterministic keyword categorization. First matching category wins.
_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("data_error", re.compile(
        r"(?i)\b(wrong number|incorrect|not \d|should be|actually it'?s|"
        r"that'?s not|inaccurate|miscalculat|wrong (figure|amount|data|value))\b")),
    ("format_preference", re.compile(
        r"(?i)\b(bullet|shorter|one[- ]line|one line|concise|brief(er)?|longer|"
        r"format|table|blue|colou?r|font|layout|too long|make it short)\b")),
    ("missing_info", re.compile(
        r"(?i)\b(forgot|missing|didn'?t include|left out|incomplete|"
        r"also include|you missed|add (the|a)?)\b")),
    ("wrong_tool", re.compile(
        r"(?i)\b(don'?t (make|need|want|create) a? ?(pdf|report|email)|"
        r"just tell me|no report|no email|no pdf|without (a )?(report|pdf))\b")),
    ("tone", re.compile(
        r"(?i)\b(too wordy|more formal|less formal|casual|polite|rude|tone|"
        r"friendl|professional)\b")),
]

# Message-opening patterns that mean "this is a correction of your last reply".
_INLINE_CORRECTION = re.compile(
    r"(?i)^\s*(no[,.! ]|nope\b|that'?s wrong|that is wrong|wrong\b|actually\b|"
    r"correction[:,]|instead\b|not quite|incorrect\b)")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB, timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init() -> None:
    try:
        c = _conn()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS feedback (
              feedback_id TEXT PRIMARY KEY,
              trace_id TEXT,
              session_id TEXT,
              rating TEXT,
              user_correction TEXT,
              original_request TEXT,
              original_response TEXT,
              category TEXT,
              applied INTEGER DEFAULT 0,
              timestamp TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_fb_session ON feedback(session_id);
            CREATE INDEX IF NOT EXISTS idx_fb_ts ON feedback(timestamp);
            """
        )
        c.commit()
        c.close()
    except Exception as e:
        print(f"[FEEDBACK] init failed (feedback disabled): {e}")


def categorize(correction: str, rating: str) -> str:
    """Deterministically bucket a correction. Positive w/o text -> 'positive'."""
    text = correction or ""
    if not text.strip():
        return "positive" if rating == "positive" else "other"
    for name, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return name
    return "other"


def is_inline_correction(message: str) -> bool:
    return bool(_INLINE_CORRECTION.match(message or ""))


def record(trace_id, session_id, rating, correction, original_request, original_response) -> dict:
    """Persist one feedback entry and return it (with category + applied flag).

    ``applied`` is True when the entry can be auto-acted-on now, i.e. a negative
    format_preference correction that main.py will turn into a preference.
    """
    category = categorize(correction, rating)
    applied = bool(rating == "negative" and category == "format_preference" and (correction or "").strip())
    entry = {
        "feedback_id": uuid.uuid4().hex[:12],
        "trace_id": trace_id,
        "session_id": session_id,
        "rating": rating,
        "user_correction": correction or "",
        "original_request": original_request or "",
        "original_response": original_response or "",
        "category": category,
        "applied": applied,
        "timestamp": _now(),
    }
    try:
        c = _conn()
        c.execute(
            "INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?,?,?)",
            (entry["feedback_id"], trace_id, session_id, rating,
             entry["user_correction"], entry["original_request"],
             entry["original_response"], category, int(applied), entry["timestamp"]),
        )
        c.commit()
        c.close()
    except Exception as e:
        print(f"[FEEDBACK] store failed: {e}")
    return entry


# ---------------------------------------------------- application (read) --- #
_STOP = {"what", "were", "the", "was", "for", "and", "you", "give", "show", "tell",
         "make", "me", "a", "an", "of", "in", "to", "is", "our", "with", "please"}


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) >= 4 and w not in _STOP}


def get_relevant_corrections(message: str, session_id: str, limit: int = 3) -> list[str]:
    """Mechanism B input: past negative corrections whose original request
    shares a keyword with the new message. Most recent first, capped."""
    try:
        want = _keywords(message)
        if not want:
            return []
        c = _conn()
        rows = c.execute(
            "SELECT user_correction, original_request FROM feedback "
            "WHERE rating='negative' AND TRIM(user_correction)!='' "
            "ORDER BY timestamp DESC LIMIT 100"
        ).fetchall()
        c.close()
        out: list[str] = []
        for r in rows:
            if want & _keywords(r["original_request"]):
                out.append(r["user_correction"])
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        print(f"[FEEDBACK] relevance lookup failed: {e}")
        return []


def recurring_issues(threshold: int = RECURRING_THRESHOLD) -> list[dict]:
    """Mechanism C: categories with >= threshold negative feedbacks."""
    try:
        c = _conn()
        rows = c.execute(
            "SELECT category, COUNT(*) n FROM feedback WHERE rating='negative' "
            "GROUP BY category HAVING n>=? ORDER BY n DESC", (threshold,)
        ).fetchall()
        c.close()
        return [
            {"category": r["category"], "count": r["n"],
             "message": f"Recurring issue: {r['category']} ({r['n']} negatives) — manual review recommended."}
            for r in rows
        ]
    except Exception as e:
        print(f"[FEEDBACK] recurring lookup failed: {e}")
        return []


def get_recent(limit: int = 20) -> list[dict]:
    try:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM feedback ORDER BY timestamp DESC, rowid DESC LIMIT ?", (int(limit),)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[FEEDBACK] recent lookup failed: {e}")
        return []


def get_for_trace(trace_id: str) -> list[dict]:
    try:
        c = _conn()
        rows = c.execute("SELECT * FROM feedback WHERE trace_id=?", (trace_id,)).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[FEEDBACK] trace lookup failed: {e}")
        return []


def get_stats() -> dict:
    try:
        c = _conn()
        total = c.execute("SELECT COUNT(*) n FROM feedback").fetchone()["n"]
        pos = c.execute("SELECT COUNT(*) n FROM feedback WHERE rating='positive'").fetchone()["n"]
        neg = total - pos
        by_cat = c.execute(
            "SELECT category, COUNT(*) n FROM feedback GROUP BY category ORDER BY n DESC"
        ).fetchall()
        common = c.execute(
            "SELECT user_correction, COUNT(*) n FROM feedback "
            "WHERE rating='negative' AND TRIM(user_correction)!='' "
            "GROUP BY user_correction ORDER BY n DESC LIMIT 5"
        ).fetchall()
        c.close()
        return {
            "total": total,
            "positive": pos,
            "negative": neg,
            "positive_pct": round(100 * pos / total, 1) if total else 0.0,
            "negative_pct": round(100 * neg / total, 1) if total else 0.0,
            "by_category": {r["category"]: r["n"] for r in by_cat},
            "common_corrections": [{"correction": r["user_correction"], "count": r["n"]} for r in common],
            "recurring_issues": recurring_issues(),
        }
    except Exception as e:
        print(f"[FEEDBACK] stats failed: {e}")
        return {"total": 0, "error": str(e)}


if __name__ == "__main__":
    init()
    assert categorize("please use bullet points", "negative") == "format_preference"
    assert categorize("that's not 45000, should be 42000", "negative") == "data_error"
    assert categorize("you forgot December", "negative") == "missing_info"
    assert categorize("just tell me the number, no PDF", "negative") == "wrong_tool"
    assert categorize("", "positive") == "positive"
    assert is_inline_correction("no, that's wrong")
    assert not is_inline_correction("what were the sales in June?")
    print("categorization + inline detection OK")

    for i in range(3):
        record(f"tr{i}", "s1", "negative", "that's not right, wrong number",
               "what were the quarterly totals?", "It was 100000.")
    print("stats:", json.dumps(get_stats(), indent=2))
    print("relevant:", get_relevant_corrections("show me the quarterly totals again", "s1"))
    Path(_DB).unlink(missing_ok=True)
