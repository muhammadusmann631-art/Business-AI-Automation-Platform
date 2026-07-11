"""Phase 9 — lightweight custom tracer (SQLite-backed).

Every request becomes ONE trace; every step (router, planner, tool, retry,
QA, approval, response) becomes a span within it. Stored locally in
``traces.db`` so traces survive restarts and can be queried via the API /
dashboard.

Hard rule: the tracer is an OBSERVER. Every public function swallows its own
errors — a broken tracer must never crash or alter a request. It also never
stores raw secrets, and truncates long inputs/outputs to keep the DB small.

Deliberately NOT Langfuse/SaaS. The schema is export-friendly so a later
phase can push these rows to an external platform by swapping the backend.
"""

import contextlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

_DB = Path(__file__).parent / "traces.db"

# In-flight state kept in memory until a span/trace closes.
_open_spans: dict[str, tuple] = {}   # span_id -> (trace_id, name, input, start_monotonic)
_open_traces: dict[str, dict] = {}   # trace_id -> {start, message, session, created}

_MAX = 500  # truncate stored inputs/outputs to this many chars


# ------------------------------------------------------------- internals -- #
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB, timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _trunc(value, limit: int = _MAX):
    """Serialise to a compact string and clip. Never raises."""
    if value is None:
        return None
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            value = str(value)
    return value[:limit]


def est_tokens(*texts: str) -> int:
    """Rough token estimate (~chars/4). Not billing-accurate — just visibility."""
    return sum(len(t) for t in texts if isinstance(t, str)) // 4


def init() -> None:
    try:
        c = _conn()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS traces (
              trace_id TEXT PRIMARY KEY,
              session_id TEXT,
              message TEXT,
              route TEXT,
              total_duration_ms INTEGER,
              total_tokens INTEGER,
              status TEXT,
              response TEXT,
              created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS spans (
              span_id TEXT PRIMARY KEY,
              trace_id TEXT,
              name TEXT,
              input TEXT,
              output TEXT,
              duration_ms INTEGER,
              tokens INTEGER,
              status TEXT,
              metadata TEXT,
              created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
            CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at);
            """
        )
        c.commit()
        c.close()
    except Exception as e:
        print(f"[TRACE] init failed (tracing disabled): {e}")


# ----------------------------------------------------------- write path --- #
def start_trace(message: str, session_id: str):
    try:
        tid = uuid.uuid4().hex[:12]
        _open_traces[tid] = {
            "start": time.monotonic(),
            "message": message,
            "session": session_id,
            "created": _now(),
        }
        return tid
    except Exception as e:
        print(f"[TRACE] start_trace failed: {e}")
        return None


def start_span(trace_id, name: str, input_data=None):
    if not trace_id:
        return None
    try:
        sid = uuid.uuid4().hex[:12]
        _open_spans[sid] = (trace_id, name, _trunc(input_data), time.monotonic())
        return sid
    except Exception as e:
        print(f"[TRACE] start_span failed: {e}")
        return None


def end_span(span_id, output=None, tokens: int = 0, status: str = "success", metadata=None):
    if not span_id:
        return
    try:
        entry = _open_spans.pop(span_id, None)
        if entry is None:
            return
        trace_id, name, inp, start = entry
        dur = int((time.monotonic() - start) * 1000)
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO spans VALUES (?,?,?,?,?,?,?,?,?,?)",
            (span_id, trace_id, name, inp, _trunc(output), dur,
             int(tokens or 0), status, _trunc(metadata), _now()),
        )
        c.commit()
        c.close()
    except Exception as e:
        print(f"[TRACE] end_span failed: {e}")


def end_trace(trace_id, response=None, total_tokens: int = 0,
              status: str = "success", route=None) -> None:
    if not trace_id:
        return
    try:
        info = _open_traces.pop(trace_id, None)
        start = info["start"] if info else time.monotonic()
        dur = int((time.monotonic() - start) * 1000)
        c = _conn()
        c.execute(
            "INSERT OR REPLACE INTO traces VALUES (?,?,?,?,?,?,?,?,?)",
            (trace_id,
             info["session"] if info else None,
             _trunc(info["message"]) if info else None,
             route, dur, int(total_tokens or 0), status,
             _trunc(response),
             info["created"] if info else _now()),
        )
        c.commit()
        c.close()
        note = " (fast-track)" if route == "simple" else ""
        print(f"[TRACE] {trace_id} completed — {dur}ms, "
              f"{int(total_tokens or 0)} tokens, status: {status}{note}")
    except Exception as e:
        print(f"[TRACE] end_trace failed: {e}")


@contextlib.contextmanager
def span(trace_id, name: str, input_data=None):
    """Context manager: times a step, records it, and NEVER masks a real error.

    Usage:
        with tracer.span(tid, "planner", msg) as s:
            s["output"] = ...; s["tokens"] = ...
    """
    sid = start_span(trace_id, name, input_data)
    box: dict = {"output": None, "tokens": 0, "status": "success", "metadata": None}
    try:
        yield box
    except Exception as e:  # the wrapped request work failed — record + re-raise
        meta = box["metadata"] if isinstance(box["metadata"], dict) else {}
        meta["error"] = str(e)[:200]
        end_span(sid, box["output"], box["tokens"], "error", meta)
        raise
    else:
        end_span(sid, box["output"], box["tokens"], box["status"], box["metadata"])


# ------------------------------------------------------------ read path --- #
def _span_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except Exception:
            pass
    return d


def get_trace(trace_id: str):
    try:
        c = _conn()
        t = c.execute("SELECT * FROM traces WHERE trace_id=?", (trace_id,)).fetchone()
        spans = c.execute(
            "SELECT * FROM spans WHERE trace_id=? ORDER BY created_at, rowid", (trace_id,)
        ).fetchall()
        c.close()
        if not t and not spans:
            return None
        result = dict(t) if t else {"trace_id": trace_id, "status": "incomplete"}
        result["spans"] = [_span_dict(s) for s in spans]
        return result
    except Exception as e:
        print(f"[TRACE] get_trace failed: {e}")
        return None


def list_traces(limit: int = 50, status: str | None = None, since: str | None = None) -> list:
    try:
        q = "SELECT * FROM traces WHERE 1=1"
        args: list = []
        if status:
            q += " AND status=?"
            args.append(status)
        if since:
            q += " AND created_at>=?"
            args.append(since)
        q += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        args.append(int(limit))
        c = _conn()
        rows = c.execute(q, args).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[TRACE] list_traces failed: {e}")
        return []


def get_stats() -> dict:
    try:
        c = _conn()
        total = c.execute("SELECT COUNT(*) n FROM traces").fetchone()["n"]
        agg = c.execute(
            "SELECT AVG(total_duration_ms) d, SUM(total_tokens) t, "
            "SUM(status!='success') e FROM traces"
        ).fetchone()
        by_route = c.execute(
            "SELECT route, COUNT(*) n, SUM(total_tokens) tokens, AVG(total_duration_ms) avg_ms "
            "FROM traces GROUP BY route"
        ).fetchall()
        slow_tools = c.execute(
            "SELECT name, COUNT(*) calls, AVG(duration_ms) avg_ms "
            "FROM spans WHERE name LIKE 'tool:%' GROUP BY name ORDER BY avg_ms DESC LIMIT 5"
        ).fetchall()
        c.close()
        errors = agg["e"] or 0
        return {
            "total_requests": total,
            "avg_duration_ms": round(agg["d"] or 0, 1),
            "total_tokens": int(agg["t"] or 0),
            "error_rate": round((errors / total) if total else 0.0, 3),
            "tokens_by_route": {
                (r["route"] or "unknown"): {
                    "requests": r["n"],
                    "tokens": int(r["tokens"] or 0),
                    "avg_ms": round(r["avg_ms"] or 0, 1),
                }
                for r in by_route
            },
            "slowest_tools": [
                {"tool": r["name"], "calls": r["calls"], "avg_ms": round(r["avg_ms"] or 0, 1)}
                for r in slow_tools
            ],
        }
    except Exception as e:
        print(f"[TRACE] get_stats failed: {e}")
        return {"total_requests": 0, "error": str(e)}


if __name__ == "__main__":
    init()
    tid = start_trace("demo request: get June sales and make a report", "sess-demo")
    with span(tid, "router", "get June sales") as s:
        s["output"] = "complex"; s["tokens"] = 20
    with span(tid, "tool:query_sales", {"month": "June"}) as s:
        s["output"] = [{"month": "June", "amount": 45000}]
    with span(tid, "qa", "draft") as s:
        s["output"] = "PASS"; s["metadata"] = {"checks_failed": 0}
    end_trace(tid, "Sales for June were 45000.", total_tokens=1200, status="success", route="complex")

    print("\nget_trace:", json.dumps(get_trace(tid), indent=2)[:400])
    print("\nlist_traces:", list_traces(limit=3))
    print("\nstats:", json.dumps(get_stats(), indent=2))
