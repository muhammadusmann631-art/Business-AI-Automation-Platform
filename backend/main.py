import os
import re
import sys
from pathlib import Path

# Make terminal logging robust to a limited console codec (Windows cp1252
# cannot encode emoji like ⚠️). Without this, an emoji in a log line raises
# UnicodeEncodeError and can turn a background log into a request failure.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import approval
import auth
import charting
import database as db
import dead_letter
import exporting
import feedback
import qa
import resilience
import router
import tracer
import whatsapp
from charting import CHARTS_DIR
from emailing import draft_email as draft_email_impl, send_email as send_email_impl
from exporting import EXPORTS_DIR
from memory import PreferenceStore, ShortTermMemory
from reporting import REPORTS_DIR, generate_report as generate_report_impl

load_dotenv()

app = FastAPI(title="AI Agent System — Auth + WhatsApp")

short_term = ShortTermMemory()
preferences = PreferenceStore(Path(__file__).parent / "preferences.json")

# Real database (Phase 4). Seed on startup so there is real data to query.
# Seeding is idempotent and uses a read-write connection; the query TOOL only
# ever touches the read-only path.
db.seed()

# Phase 9: initialise the trace store (separate traces.db). Safe/idempotent.
tracer.init()

# Phase 10: initialise the feedback store (feedback.db). Safe/idempotent.
feedback.init()

# Auth: seed the default admin user once (idempotent).
auth.ensure_admin()

# Phase 10: last completed trace per session, so an inline correction ("no,
# that's wrong...") can be linked to the response it is correcting.
_LAST_TRACE: dict[str, str] = {}

# Base URL used to turn a generated report path into a downloadable link.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

app.add_middleware(
    CORSMiddleware,
    # Deployment: allow all origins for now (the frontend also proxies /api via
    # Next.js rewrites, so most calls are same-origin). Restrict once auth lands.
    # credentials must be False with a wildcard origin (we use no cookies).
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------------- #
# Auth middleware — protect every /api/* route except the public ones. A valid
# `Authorization: Bearer <jwt>` is required; otherwise 401. Static files and
# the auth/whatsapp/health endpoints stay public.
# --------------------------------------------------------------------------- #
_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect"}
_PUBLIC_PREFIXES = ("/api/auth/", "/reports/", "/exports/", "/charts/")
_PUBLIC_EXACT = {"/api/whatsapp"}  # Twilio webhook — validated by signature, not JWT


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    request.state.user = auth.current_user(request.headers.get("authorization"))

    is_public = (
        request.method == "OPTIONS"
        or not path.startswith("/api/")
        or path in _PUBLIC_PATHS
        or path in _PUBLIC_EXACT
        or any(path.startswith(p) for p in _PUBLIC_PREFIXES)
    )
    if not is_public and request.state.user is None:
        return JSONResponse(
            status_code=401, content={"detail": "Not authenticated. Please log in."}
        )
    return await call_next(request)


# Serve generated artifacts so the reply can link to / render them.
REPORTS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)
CHARTS_DIR.mkdir(exist_ok=True)
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")
app.mount("/exports", StaticFiles(directory=EXPORTS_DIR), name="exports")   # Level 1: Excel
app.mount("/charts", StaticFiles(directory=CHARTS_DIR), name="charts")      # Level 1: charts


# --------------------------------------------------------------------------- #
# Phase 6 — failure handling: per-request context, fault injection, guarded()
# --------------------------------------------------------------------------- #

# Per-request context for dead-lettering (Phase 6) and pending approvals
# (Phase 7). This is a single-user dev server, so a module-level dict is fine;
# it is reset at the start of every request.
_REQUEST_CTX: dict = {
    "request": "",
    "session_id": "default",
    "failures": [],
    "pending": [],       # approval.Pending entries created during this request
    "trace_id": None,    # Phase 9: current request's trace (None -> spans no-op)
    "tokens": 0,         # Phase 9: accumulated approximate token count
    "files": [],         # Polish: downloadable files (PDFs) produced this request
    "send_intent": False, # Polish: user explicitly asked to SEND an email
}


def _acct(n: int) -> None:
    """Add to the request's running approximate token total (Phase 9)."""
    _REQUEST_CTX["tokens"] = _REQUEST_CTX.get("tokens", 0) + int(n or 0)


# Polish Fix 2: detect a genuine "send this email" intent from the user's own
# words, so the human-approval gate fires even when the LLM only drafts. Covers
# English + romanized Hindi/Urdu. A "draft only / don't send" phrase overrides.
_SEND_VERB = re.compile(r"(?i)(\bsend\b|\bbhej|mail\s*kar|email\s*kar|forward\b|deliver\b)")
_EMAIL_CTX = re.compile(r"(?i)(email|e-mail|\bmail\b|@)")
_NO_SEND = re.compile(r"(?i)(draft only|just draft|only draft|don'?t send|do not send|na bhej|mat bhej)")


def _detect_send_intent(message: str) -> bool:
    if _NO_SEND.search(message or ""):
        return False
    return bool(_SEND_VERB.search(message or "") and _EMAIL_CTX.search(message or ""))

# Dev/test-only fault injector, armed from a `force_fail=...` directive in the
# incoming message and cleared after each request. NOT a production feature.
_FAULT: dict = {"tool": None, "mode": None, "remaining": 0}

_TOOL_ALIASES = {
    "sql": "query_sales", "query_sales": "query_sales",
    "report": "generate_report", "pdf": "generate_report",
    "generate_report": "generate_report",
    "email": "draft_email", "draft_email": "draft_email",
    "pref": "save_preference", "save_preference": "save_preference",
}
_FAULT_RE = re.compile(r"force_fail=(\w+)(?::(\w+))?(?::(\d+))?", re.IGNORECASE)


def _parse_fault(message: str) -> tuple[str, dict | None]:
    """Pull a `force_fail=<tool>[:<mode>[:<n>]]` test directive out of a message.

    Modes: ``recover`` (fail N times then succeed — proves retry recovery),
    ``exhaust`` (always transient — proves dead-letter + alert), ``permanent``
    (fail immediately, no retry). Returns the cleaned message + the fault dict.
    """
    m = _FAULT_RE.search(message)
    if not m:
        return message, None
    tool = _TOOL_ALIASES.get(m.group(1).lower(), m.group(1).lower())
    mode = (m.group(2) or "exhaust").lower()
    n = int(m.group(3)) if m.group(3) else 2
    fault = {"tool": tool, "mode": mode, "remaining": n if mode == "recover" else 0}
    cleaned = _FAULT_RE.sub("", message).strip()
    return (cleaned or message), fault


def _arm_fault(fault: dict | None) -> None:
    _FAULT.update(fault or {"tool": None, "mode": None, "remaining": 0})
    if fault:
        print(f"[FAULT-INJECT] armed (dev/test only): {fault}")


def _maybe_inject_fault(tool_name: str) -> None:
    """Raise a fake error if a fault is armed for this tool (dev/test only)."""
    f = _FAULT
    if f["tool"] != tool_name:
        return
    if f["mode"] == "permanent":
        raise ValueError("invalid request (injected permanent fault)")
    if f["mode"] == "recover" and f["remaining"] > 0:
        f["remaining"] -= 1
        raise TimeoutError("connection timed out (injected transient fault)")
    if f["mode"] == "exhaust":
        raise TimeoutError("connection timed out (injected transient fault)")
    # recover mode with no remaining failures -> fall through and succeed.


def guarded(tool_name: str, fn, dedup_key: str | None = None):
    """Run a tool's real work with retry + backoff, dead-lettering on exhaustion.

    Returns ``(True, result)`` on success or ``(False, user_message)`` on
    failure. Every unrecovered failure is recorded on the request context so
    the Phase 5 QA layer can flag it to the user.

    ``dedup_key`` (Part 1 fix): if the SAME tool+args ran already this request,
    return the cached result instead of running again — a safety net so a
    double-calling LLM never produces duplicate charts/PDFs/Excels/emails.
    """
    tid = _REQUEST_CTX.get("trace_id")

    calls: dict = _REQUEST_CTX.setdefault("tool_calls", {})
    if dedup_key is not None and dedup_key in calls:
        print(f"[DEDUP] skipping duplicate call: {tool_name}")
        return True, calls[dedup_key]

    def _do():
        _maybe_inject_fault(tool_name)
        return fn()

    def _on_retry(attempt, wait, error):
        # Phase 9: record each retry attempt as its own short span.
        sid = tracer.start_span(tid, f"retry:{tool_name}", {"attempt": attempt + 1, "wait_s": wait})
        tracer.end_span(sid, {"error": str(error)[:200]}, status="retry")

    with tracer.span(tid, f"tool:{tool_name}") as sp:
        try:
            result = resilience.call_with_retry(_do, tool_name=tool_name, on_retry=_on_retry)
            sp["output"] = result
            if dedup_key is not None:
                calls[dedup_key] = result  # cache for the dedup safety net
            return True, result
        except resilience.RetryExhausted as e:
            # Transient failure survived all retries -> save it, alert, flag it.
            sp["status"] = "error"
            sp["metadata"] = {"attempts": e.attempts, "error": str(e.last_error)[:200]}
            dead_letter.save(
                request=_REQUEST_CTX["request"],
                tool=tool_name,
                error=e.last_error,
                attempts=e.attempts,
                session_id=_REQUEST_CTX["session_id"],
            )
            _REQUEST_CTX["failures"].append(
                {"tool": tool_name, "attempts": e.attempts, "error": str(e.last_error)}
            )
            return False, (
                f"[TOOL FAILED] The '{tool_name}' step could not be completed after "
                f"{e.attempts} attempts. It has been logged for review."
            )
        except Exception as e:
            # Permanent error: not retried and not dead-lettered (a retry won't
            # help), but the user still gets a clean message instead of a crash.
            sp["status"] = "error"
            sp["metadata"] = {"error": str(e)[:200], "permanent": True}
            print(f"[TOOL FAILED] {tool_name} permanent error (not retried): {e}")
            _REQUEST_CTX["failures"].append(
                {"tool": tool_name, "attempts": 1, "error": str(e), "permanent": True}
            )
            return False, f"[TOOL FAILED] The '{tool_name}' step failed: {e}"


@function_tool
def query_sales(month: str) -> str:
    """Look up the REAL sales figure for a given month from the database.

    Runs a read-only SELECT against the real database. Use this whenever the
    user asks about sales numbers. Do not guess figures from memory.

    Args:
        month: The month name in English, e.g. "June".
    """
    print(f"[TOOL CALLED] sql read-only: sales for {month}")
    ok, out = guarded("query_sales", lambda: db.query_sales(month))
    if not ok:
        return out
    rows = out
    if not rows:
        return f"No sales data available for {month}."
    return f"Sales for {rows[0]['month']} were {rows[0]['amount']}."


@function_tool
def generate_report(title: str, body: str) -> str:
    """Generate a real downloadable PDF report and return its link.

    Use this when the user asks for a report/PDF. Put the actual figures and
    summary into `body` (use results from earlier steps — do not invent data).

    Args:
        title: Report title, e.g. "June Sales Report".
        body: The full report text/summary to place in the PDF.
    """
    ok, out = guarded("generate_report", lambda: generate_report_impl(title, body),
                      dedup_key=f"generate_report:{title}:{body[:120]}")
    if not ok:
        return out
    result = out
    print(f"[TOOL CALLED] generate_report -> {result['filename']}")
    url = f"{PUBLIC_BASE_URL}/reports/{result['filename']}"
    # Polish Fix 1: surface the PDF as a structured file so the frontend can
    # render a real download card (not just link text buried in the reply).
    _REQUEST_CTX.setdefault("files", []).append(
        {"name": result["filename"], "url": f"/reports/{result['filename']}", "type": "pdf"}
    )
    return f"PDF report created: {url} (saved at {result['path']})"


@function_tool
def draft_email(to: str, subject: str, body: str, attachment: str = "", send: bool = False) -> str:
    """Compose an email DRAFT, and optionally queue it for SENDING.

    Use this when the user asks to email/draft a message. The tool itself
    NEVER sends. If the user explicitly asked to actually SEND the email
    (not just draft it), set send=true: the draft is then queued for human
    approval, and only a human clicking Approve triggers the real send.

    Args:
        to: Recipient email address.
        subject: Subject line.
        body: Email body text.
        attachment: Optional report filename/link to reference.
        send: True ONLY if the user explicitly asked to send (not just draft).
    """
    ok, out = guarded("draft_email", lambda: draft_email_impl(to, subject, body, attachment),
                      dedup_key=f"draft_email:{to}:{subject}")
    if not ok:
        return out
    draft = out
    print(f"[TOOL CALLED] draft_email (NOT sent) -> {draft['to']}")
    lines = [
        "EMAIL DRAFT (not sent):",
        f"To: {draft['to']}",
        f"Subject: {draft['subject']}",
    ]
    if draft["attachment"]:
        lines.append(f"Attachment: {draft['attachment']}")
    lines.append("")
    lines.append(draft["body"])

    # Phase 7: sending is high-risk -> park it for human approval. The real
    # send happens ONLY in /api/approve, never here.
    # Polish Fix 2: honour the LLM's send flag OR a deterministic send-intent
    # detected from the user's own words, so approval never gets skipped.
    should_send = bool(send) or _REQUEST_CTX.get("send_intent", False)
    if should_send and approval.classify_risk("send_email") == approval.REQUIRES_APPROVAL:
        _asid = tracer.start_span(
            _REQUEST_CTX.get("trace_id"), "approval", {"action": "send_email", "to": draft["to"]}
        )
        entry = approval.create_pending(
            action="send_email",
            details={
                "to": draft["to"],
                "subject": draft["subject"],
                "body": draft["body"],
                "attachment": draft["attachment"] or "",
            },
            execute=lambda: send_email_impl(
                draft["to"], draft["subject"], draft["body"], draft["attachment"] or ""
            ),
            session_id=_REQUEST_CTX["session_id"],
            reason=approval.risk_reason("send_email"),
        )
        _REQUEST_CTX["pending"].append(entry)
        tracer.end_span(_asid, {"approval_id": entry.approval_id}, status="pending")
        lines.append("")
        lines.append(
            f"[AWAITING APPROVAL] This email will be sent only after you approve it "
            f"(id: {entry.approval_id})."
        )
    return "\n".join(lines)


@function_tool
def save_preference(key: str, value: str) -> str:
    """Persist a lasting user preference so it applies in future conversations.

    Use this only when the user states a durable preference, e.g.
    "always keep graphs blue" or "from now on reply in short bullet points".
    Do not use it for one-off requests.

    Args:
        key: Short snake_case name for the preference, e.g. "graph_color".
        value: The preferred value, e.g. "blue".
    """
    ok, out = guarded("save_preference", lambda: preferences.save(key, value))
    if not ok:
        return out
    return f"Preference saved: {key} = {value}."


# Schema summary reused in tool docstrings + agent instructions.
_SCHEMA_HINT = (
    "Tables & columns:\n"
    "- sales(month, amount, customer_id)\n"
    "- customers(id, name, email, company, phone, city, status[active|inactive|lead])\n"
    "- invoices(id, invoice_number, customer_id, amount, status[pending|paid|overdue|"
    "cancelled], due_date, paid_date, description)\n"
    "- products(id, name, category, price, stock, status[active|discontinued])\n"
    "- expenses(id, category[salary|rent|utilities|marketing|supplies|other], amount, "
    "description, date)"
)


def _format_rows(rows: list[dict], limit: int = 50) -> str:
    """Compact text table of query results for the LLM to read."""
    if not rows:
        return "Query returned no rows."
    cols = list(rows[0].keys())
    lines = [" | ".join(cols)]
    for r in rows[:limit]:
        lines.append(" | ".join(str(r.get(c, "")) for c in cols))
    if len(rows) > limit:
        lines.append(f"... ({len(rows) - limit} more rows)")
    lines.append(f"[{len(rows)} row(s)]")
    return "\n".join(lines)


def _chart_color() -> str:
    """Honour a saved colour preference for charts (e.g. 'graphs blue')."""
    prefs = preferences.all()
    for k in ("graph_color", "chart_color", "graphs", "color"):
        if prefs.get(k):
            return prefs[k]
    return "#43e0a3"


@function_tool
def query_database(sql: str) -> str:
    """Run a READ-ONLY SQL SELECT against the business database and return rows.

    Use this for ANY data question about customers, invoices, products,
    expenses, or sales. Write a single standard SQLite SELECT (you may use
    JOIN, WHERE, GROUP BY, ORDER BY, aggregates). Writes are impossible — only
    SELECT is allowed. See the worker instructions for the full schema.

    Args:
        sql: One read-only SELECT statement.
    """
    print(f"[TOOL CALLED] query_database: {sql[:120]}")
    try:
        db._ensure_read_only(sql)
    except db.UnsafeQueryError as e:
        return f"Query rejected (read-only): {e}"
    ok, out = guarded("query_database", lambda: db.run_select(sql), dedup_key=f"query_database:{sql}")
    if not ok:
        return out
    return _format_rows(out)


@function_tool
def export_excel(query: str, title: str) -> str:
    """Export the result of a read-only SQL SELECT to a downloadable Excel file.

    Use when the user asks for data "in Excel"/".xlsx". Write a SELECT that
    returns the columns to export.

    Args:
        query: A read-only SELECT whose rows become the spreadsheet.
        title: Short title for the file, e.g. "Overdue Invoices".
    """
    print(f"[TOOL CALLED] export_excel: {title}")
    try:
        db._ensure_read_only(query)
    except db.UnsafeQueryError as e:
        return f"Query rejected (read-only): {e}"

    def _do():
        rows = db.run_select(query)
        return exporting.export_rows(title, rows)

    ok, out = guarded("export_excel", _do, dedup_key=f"export_excel:{title}:{query}")
    if not ok:
        return out
    _REQUEST_CTX.setdefault("files", []).append(
        {"name": out["filename"], "url": f"/exports/{out['filename']}", "type": "excel"}
    )
    return f"Excel file created: {PUBLIC_BASE_URL}/exports/{out['filename']}"


@function_tool
def make_chart(query: str, title: str, chart_type: str = "bar") -> str:
    """Create a bar or line chart image from a read-only SQL SELECT.

    The query MUST return two columns: a label (first column) and a numeric
    value (second column). Example for 6-month sales:
    "SELECT month, amount FROM sales". The user's saved colour preference is
    applied automatically.

    Args:
        query: A read-only SELECT returning (label, value) rows.
        title: Chart title, e.g. "Last 6 Months Sales".
        chart_type: "bar" (default) or "line".
    """
    print(f"[TOOL CALLED] make_chart: {title} ({chart_type})")
    try:
        db._ensure_read_only(query)
    except db.UnsafeQueryError as e:
        return f"Query rejected (read-only): {e}"

    def _do():
        rows = db.run_select(query)
        if not rows:
            raise ValueError("query returned no data to chart")
        cols = list(rows[0].keys())
        value_col = cols[1] if len(cols) > 1 else cols[0]
        labels = [r[cols[0]] for r in rows]
        values = [r[value_col] for r in rows]
        return charting.make_chart(title, labels, values, chart_type, _chart_color())

    ok, out = guarded("make_chart", _do, dedup_key=f"make_chart:{title}:{query}:{chart_type}")
    if not ok:
        return out
    _REQUEST_CTX.setdefault("files", []).append(
        {"name": out["filename"], "url": f"/charts/{out['filename']}", "type": "chart"}
    )
    return f"Chart created: {PUBLIC_BASE_URL}/charts/{out['filename']}"


@function_tool
def compare_data(query_a: str, label_a: str, query_b: str, label_b: str) -> str:
    """Compare two read-only SQL numeric results and show the change/percentage.

    Each query should return a single numeric total, e.g.
    "SELECT SUM(amount) FROM sales WHERE month='June'".

    Args:
        query_a: Read-only SELECT for the first value.
        label_a: Human label for the first value, e.g. "June".
        query_b: Read-only SELECT for the second value.
        label_b: Human label for the second value, e.g. "July".
    """
    print(f"[TOOL CALLED] compare_data: {label_a} vs {label_b}")
    for q in (query_a, query_b):
        try:
            db._ensure_read_only(q)
        except db.UnsafeQueryError as e:
            return f"Query rejected (read-only): {e}"

    def _num(q: str) -> float:
        rows = db.run_select(q)
        if not rows:
            return 0.0
        for c in rows[0].keys():
            try:
                return float(sum(float(r[c] or 0) for r in rows))
            except (TypeError, ValueError):
                continue
        return 0.0

    ok, out = guarded("compare_data", lambda: (_num(query_a), _num(query_b)))
    if not ok:
        return out
    a, b = out
    diff = b - a
    pct = (diff / a * 100) if a else 0.0
    arrow = "increase" if diff > 0 else ("decrease" if diff < 0 else "no change")
    return (
        f"Comparison:\n"
        f"- {label_a}: {a:,.0f}\n"
        f"- {label_b}: {b:,.0f}\n"
        f"- Difference: {diff:+,.0f} ({pct:+.1f}% {arrow})"
    )


sales_agent = Agent(
    name="Worker",
    instructions=(
        "You are AGI-CORE's worker agent executing ONE step of a plan. You "
        "understand English, Urdu, and Roman Urdu (Hinglish); reply in the "
        "user's language. Pick the right tool:\n"
        "- Any data question (sales, customers, invoices, products, expenses): "
        "use query_database with a read-only SQL SELECT. NEVER guess numbers. "
        "For name/text searches use LIKE with % wildcards and COLLATE NOCASE "
        "(e.g. WHERE name LIKE '%Ahmed%' COLLATE NOCASE) so partial and "
        "case-insensitive matches work.\n"
        "- Excel/.xlsx export: use export_excel with a SELECT for the data.\n"
        "- Chart/graph: use make_chart with a SELECT returning (label, value).\n"
        "- Compare two periods/values: use compare_data.\n"
        "- Report/PDF: use generate_report, putting REAL figures from earlier "
        "steps into the body. Return the link it gives you.\n"
        "- Email: use draft_email. If the user asked to SEND, set send=true — "
        "a human must approve before anything is sent.\n"
        "- Lasting user preference (e.g. 'graphs blue'): use save_preference "
        "with a clear key like graph_color.\n"
        + _SCHEMA_HINT + "\n"
        "IMPORTANT: Call each tool ONLY ONCE per step. Never call the same "
        "tool twice with the same or similar parameters. Once you have a "
        "tool's result, USE it — do not call the tool again. One chart, one "
        "PDF, one Excel, one email draft per request.\n"
        "Format numbers with commas/currency where sensible. Reply with only "
        "the result of this step, briefly."
    ),
    model="gpt-4o-mini",
    tools=[
        query_database, query_sales, export_excel, make_chart, compare_data,
        generate_report, draft_email, save_preference,
    ],
)


class Plan(BaseModel):
    steps: list[str]


planner_agent = Agent(
    name="Planner",
    instructions=(
        "You break a user request into a short ordered list of steps for other "
        "agents to execute. Rules:\n"
        "- Use as few steps as possible: 1 step for a simple message or "
        "greeting, 2-4 steps only when the request genuinely has parts.\n"
        "- Each step is one short imperative sentence.\n"
        "- Use the conversation history in the input to resolve references "
        'like "that" or "it" — write steps that name the actual thing.\n'
        "- If the user states a lasting preference (\"always ...\", \"from "
        'now on ..."), include a step to save that preference.\n'
        "- The available actions are: query the business database (sales, "
        "customers, invoices, products, expenses), export data to Excel, make "
        "a chart/graph, compare two values, generate a PDF report, draft/send "
        "an email (sending needs human approval, after the plan), and save a "
        "preference. Plan a DATA step BEFORE any step (chart, Excel, report, "
        "email) that needs that data. Do not plan steps needing any other "
        "capability (no web search).\n"
        "- NEVER create duplicate steps. Each tool/action appears AT MOST "
        "ONCE (never two chart steps or two PDF steps). Max 2-4 steps."
    ),
    model="gpt-4o-mini",
    output_type=Plan,
)

supervisor_agent = Agent(
    name="Supervisor",
    instructions=(
        "You are AGI-CORE, a professional AI business assistant that helps "
        "businesses with data analysis, reporting, and communication. You are "
        "given the user's original request, conversation context, and the "
        "results of the executed plan steps. Combine them into ONE clear, "
        "natural final reply.\n"
        "Behaviour rules:\n"
        "- You understand English, Urdu, and Roman Urdu (Hinglish). Reply in "
        "the SAME language the user used.\n"
        "- Be professional but friendly; concise and actionable.\n"
        "- Format numbers properly (commas, currency symbols where sensible).\n"
        "- Use ONLY the data from the step results — never invent numbers.\n"
        "- If a download link or chart was produced, mention it naturally.\n"
        "- Respect known user preferences. Do not mention the plan, the steps, "
        "or other agents."
    ),
    model="gpt-4o-mini",
)

# Phase 8: fast-track agent for SIMPLE requests — no tools, no planning.
# One direct call, like Phase 0 but with memory context and PII protection.
chat_agent = Agent(
    name="Assistant",
    instructions=(
        "You are a friendly, concise assistant. Answer the user directly "
        "using the conversation context provided. Respect any known user "
        "preferences. Do not invent business data — if the user needs real "
        "sales figures, reports, or emails, tell them to ask for that "
        "explicitly."
    ),
    model="gpt-4o-mini",
)


def build_memory_context(session_id: str) -> str:
    """Assemble stored preferences + recent history into a context block."""
    history = short_term.history(session_id)
    prefs = preferences.all()
    print(f"[MEMORY] session {session_id} has {len(history)} prior turns")

    lines: list[str] = []
    if prefs:
        lines.append(
            "Known user preferences: "
            + ", ".join(f"{k}={v}" for k, v in prefs.items())
        )
    if history:
        lines.append("Conversation so far:")
        for turn in history[-6:]:
            lines.append(f"User: {turn['user']}")
            lines.append(f"Assistant: {turn['assistant']}")
    return "\n".join(lines)


async def _execute_step(
    i: int,
    step: str,
    prior_results: list[str],
    message: str,
    memory_context: str,
    total: int,
) -> str:
    """Run one plan step through the worker, given the results before it."""
    print(f"[STEP {i}/{total}] {step}")
    context = "\n".join(
        f"Result of step {j}: {r}" for j, r in enumerate(prior_results, 1)
    )
    worker_input = (
        f"{memory_context}\n"
        f"User request: {message}\n"
        f"{context}\n"
        f"Your step to execute now: {step}"
    )
    with tracer.span(_REQUEST_CTX.get("trace_id"), f"step:{i}", step) as sp:
        result = await Runner.run(sales_agent, input=worker_input)
        out = str(result.final_output or "")
        sp["output"] = out
        sp["tokens"] = tracer.est_tokens(worker_input, out)
        _acct(sp["tokens"])
        return out


async def _combine(
    steps: list[str], step_results: list[str], message: str, memory_context: str
) -> str:
    """Supervisor combines the step results into one draft final reply."""
    supervisor_input = (
        f"{memory_context}\n"
        f"User request: {message}\n"
        + "\n".join(
            f"Step {j} ({s}): {r}"
            for j, (s, r) in enumerate(zip(steps, step_results), 1)
        )
        + "\nWrite the final reply to the user."
    )
    with tracer.span(_REQUEST_CTX.get("trace_id"), "supervisor", "combine step results") as sp:
        final = await Runner.run(supervisor_agent, input=supervisor_input)
        out = str(final.final_output or "")
        sp["output"] = out
        sp["tokens"] = tracer.est_tokens(supervisor_input, out)
        _acct(sp["tokens"])
        return out


async def run_supervised(raw_message: str, session_id: str) -> tuple[str, dict | None]:
    """Supervisor flow: recall memory, plan, execute steps, combine, THEN QA.

    Phase 5 adds the QA gate: the draft answer is reviewed before it reaches
    the user (PII redaction, a single retry on fixable issues, else a
    [QA WARNING]). Phase 6 adds resilience: each tool call is wrapped with
    retry+backoff and dead-lettered on exhaustion; unrecovered tool failures
    are handed to QA so the user is warned instead of getting a crash.
    Phase 7 adds human-in-the-loop: a high-risk step (email send) is parked
    as a pending approval instead of executing; the second element of the
    returned tuple carries it to the frontend for an Approve/Reject decision.
    """
    # Phase 6: pull any dev/test fault directive, set the request context that
    # dead-lettering needs, and reset the per-request failure/pending lists.
    message, fault = _parse_fault(raw_message)
    _REQUEST_CTX["request"] = message
    _REQUEST_CTX["session_id"] = session_id
    _REQUEST_CTX["failures"] = []
    _REQUEST_CTX["pending"] = []
    _arm_fault(fault)
    try:
        memory_context = build_memory_context(session_id)
        tid = _REQUEST_CTX.get("trace_id")

        # Phase 10 Mechanism B: inject relevant past corrections as context so
        # the plan/response reflect them, without changing any pipeline code.
        corrections = feedback.get_relevant_corrections(message, session_id)
        if corrections:
            print(f"[FEEDBACK] injecting {len(corrections)} past correction(s) as context")
            notes = "\n".join(f"- {c}" for c in corrections)
            memory_context = (
                f"{memory_context}\nNotes from past feedback on similar requests "
                f"(apply these):\n{notes}"
            )

        with tracer.span(tid, "planner", message) as sp:
            plan_result = await Runner.run(
                planner_agent,
                input=f"{memory_context}\n\nNew user request: {message}",
            )
            steps = plan_result.final_output.steps or [message]
            sp["output"] = steps
            sp["tokens"] = tracer.est_tokens(memory_context, message, *steps)
            _acct(sp["tokens"])
        print("[PLAN] " + "  ".join(f"{i}. {s}" for i, s in enumerate(steps, 1)))

        step_results: list[str] = []
        for i, step in enumerate(steps, 1):
            step_results.append(
                await _execute_step(i, step, step_results, message, memory_context, len(steps))
            )

        reply = await _combine(steps, step_results, message, memory_context)

        # --- Phase 5 QA gate. Never let a QA hiccup crash the request. ---
        try:
            failures = _REQUEST_CTX["failures"]
            with tracer.span(tid, "qa", "draft answer") as sp:
                result = qa.review(reply, step_results, steps, tool_failures=failures)
                sp["output"] = "PASS" if result.passed else "FAIL"
                sp["status"] = "success" if result.passed else "warning"
                sp["metadata"] = {
                    "checks_failed": len(result.findings),
                    "findings": [f.reason for f in result.findings][:5],
                    "redactions": result.redactions,
                }
            reply = result.answer  # use the (possibly PII-redacted) version

            if not result.passed:
                step_idx = result.fixable_step
                if step_idx is not None:
                    print(f"[QA] RETRY: re-running step {step_idx}")
                    prior = step_results[: step_idx - 1]
                    step_results[step_idx - 1] = await _execute_step(
                        step_idx, steps[step_idx - 1], prior, message, memory_context, len(steps)
                    )
                    reply = await _combine(steps, step_results, message, memory_context)
                    result = qa.review(
                        reply, step_results, steps, tool_failures=_REQUEST_CTX["failures"]
                    )
                    reply = result.answer

                if not result.passed:
                    issues = result.warning_text()
                    print(f"[QA] WARNING: {issues}")
                    reply = f"{reply}\n\n[QA WARNING] {issues}"
        except Exception as e:
            # QA must degrade gracefully — return the un-gated draft, not a 500.
            print(f"[QA] review skipped due to error: {e}")

        short_term.add_turn(session_id, message, reply)

        # Phase 8: rough cost visibility. ~overhead per LLM call (planner +
        # each worker step + supervisor) plus the text actually shuttled.
        router.log_cost(
            "full pipeline",
            memory_context, message, reply, *step_results,
            overhead=300 * (len(steps) + 2),
        )

        # Phase 7: surface a pending approval (if a high-risk step was parked)
        # so the frontend can render Approve/Reject. One at a time is enough.
        pending_payload = None
        if _REQUEST_CTX["pending"]:
            entry = _REQUEST_CTX["pending"][0]
            pending_payload = {
                "approval_id": entry.approval_id,
                "action": entry.action,
                "details": entry.details,
                "risk_reason": entry.risk_reason,
            }
        return reply, pending_payload
    finally:
        _arm_fault(None)  # always disarm the test fault after the request


async def run_fast_track(message: str, session_id: str) -> str:
    """Phase 8 SIMPLE path: ONE direct LLM call, no Planner/tools/Supervisor.

    Still memory-aware (Phase 3) and PII-safe (Phase 5's redactor), but skips
    everything that only matters when tools run.
    """
    tid = _REQUEST_CTX.get("trace_id")
    memory_context = build_memory_context(session_id)
    with tracer.span(tid, "fast_track", message) as sp:
        result = await Runner.run(
            chat_agent,
            input=f"{memory_context}\n\nUser: {message}",
        )
        reply = qa.pii_only(str(result.final_output or ""))
        sp["output"] = reply
        sp["tokens"] = tracer.est_tokens(memory_context, message, reply)
        _acct(sp["tokens"])
    short_term.add_turn(session_id, message, reply)
    router.log_cost("simple fast-track", memory_context, message, reply, overhead=100)
    return reply


async def run_routed(message: str, session_id: str) -> tuple[str, dict | None, str | None, list]:
    """Phase 8 entry + Phase 9 trace: classify, then fast-track or full pipeline.

    Owns the trace lifecycle — opens the trace, records router + response
    spans, and closes it with the accumulated duration/tokens/status. All
    tracing is best-effort and never changes the request's outcome.
    """
    # Phase 10: an inline correction ("no, that's wrong...") is feedback on the
    # previous response in this session. Record it, then process normally.
    if feedback.is_inline_correction(message) and _LAST_TRACE.get(session_id):
        try:
            _submit_feedback(_LAST_TRACE[session_id], session_id, "negative", message)
        except Exception as e:
            print(f"[FEEDBACK] inline capture failed: {e}")

    tid = tracer.start_trace(message, session_id)
    _REQUEST_CTX["trace_id"] = tid
    _REQUEST_CTX["tokens"] = 0
    _REQUEST_CTX["files"] = []                                   # Polish Fix 1
    _REQUEST_CTX["send_intent"] = _detect_send_intent(message)   # Polish Fix 2
    _REQUEST_CTX["tool_calls"] = {}                              # Part 1: dedup cache
    route, status, reply, pending = "complex", "success", "", None
    try:
        history = short_term.history(session_id)
        history_text = "\n".join(
            f"User: {t['user']}\nAssistant: {t['assistant']}" for t in history[-6:]
        )
        with tracer.span(tid, "router", message) as sp:
            decision, reason = await router.classify(message, history_text)
            sp["output"] = decision
            sp["tokens"] = tracer.est_tokens(message) + 15
            sp["metadata"] = {"reason": reason}
            _acct(sp["tokens"])
        route = decision

        if decision == router.SIMPLE:
            reply = await run_fast_track(message, session_id)
        else:
            reply, pending = await run_supervised(message, session_id)

        with tracer.span(tid, "response") as sp:
            sp["output"] = reply
            sp["status"] = "delivered"
        if tid:
            _LAST_TRACE[session_id] = tid  # for a future inline correction
        # Part 1 Fix D: dedup the files array by url (belt-and-suspenders).
        seen_urls: set[str] = set()
        unique_files = []
        for f in _REQUEST_CTX.get("files", []):
            if f["url"] not in seen_urls:
                seen_urls.add(f["url"])
                unique_files.append(f)
        return reply, pending, tid, unique_files
    except Exception:
        status = "error"
        raise
    finally:
        tracer.end_trace(tid, reply, _REQUEST_CTX.get("tokens", 0), status, route)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    pending_approval: dict | None = None  # Phase 7: set when a decision is needed
    trace_id: str | None = None           # Phase 9: correlate with the dashboard
    files: list[dict] = []                 # Polish Fix 1: downloadable outputs


class ApprovalRequest(BaseModel):
    approval_id: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------- Auth endpoints ---------------------------- #
@app.post("/api/auth/signup")
def api_signup(req: SignupRequest):
    try:
        user = auth.signup(req.name, req.email, req.password)
        print(f"[AUTH] signup: {user['email']}")
        return {"user": user}
    except auth.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signup failed: {e}")


@app.post("/api/auth/login")
def api_login(req: LoginRequest):
    try:
        token, user = auth.login(req.email, req.password)
        print(f"[AUTH] login: {user['email']}")
        return {"token": token, "user": user}
    except auth.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/api/auth/me")
def api_me(request: Request):
    u = getattr(request.state, "user", None)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"user": {"id": u["sub"], "name": u["name"], "email": u["email"], "role": u["role"]}}


def _user_session(request: Request, session_id: str) -> str:
    """Isolate memory per authenticated user (Phase 3 memory becomes per-user)."""
    u = getattr(request.state, "user", None)
    return f"u{u['sub']}:{session_id}" if u else session_id


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not set. Add it to backend/.env",
        )
    try:
        sid = _user_session(request, req.session_id)
        reply, pending, trace_id, files = await run_routed(req.message, sid)
        return ChatResponse(reply=reply, pending_approval=pending, trace_id=trace_id, files=files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}")


@app.get("/api/traces")
def api_traces(limit: int = 50, status: str | None = None, since: str | None = None):
    """Phase 9: list recent traces (summaries), newest first."""
    return {"traces": tracer.list_traces(limit=limit, status=status, since=since)}


@app.get("/api/traces/{trace_id}")
def api_trace(trace_id: str):
    """Phase 9: one full trace with all its spans."""
    trace = tracer.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return trace


@app.get("/api/stats")
def api_stats():
    """Phase 9: aggregate observability stats."""
    return tracer.get_stats()


def _submit_feedback(trace_id: str, session_id: str, rating: str, correction: str) -> dict:
    """Store feedback and run the three application mechanisms. Never raises."""
    # Pull the original request/response from the linked trace (Phase 9).
    original_request = original_response = ""
    trace = tracer.get_trace(trace_id) if trace_id else None
    if trace:
        original_request = trace.get("message") or ""
        original_response = trace.get("response") or ""

    entry = feedback.record(
        trace_id, session_id, rating, correction, original_request, original_response
    )

    if rating == "positive":
        print("[FEEDBACK] received: positive")
    else:
        print(f'[FEEDBACK] received: negative — category: {entry["category"]}'
              + (f' — "{correction}"' if correction else ""))

    # Mechanism A: a format correction becomes a durable preference (Phase 3).
    if entry["applied"]:
        preferences.save("response_style", correction.strip())
        print(f'[FEEDBACK] auto-saved preference: "{correction.strip()}"')

    # Mechanism C: surface recurring problems.
    for issue in feedback.recurring_issues():
        print(f'[FEEDBACK] ⚠️ recurring issue flagged: {issue["category"]} '
              f'({issue["count"]} negatives)')

    return entry


class FeedbackRequest(BaseModel):
    trace_id: str | None = None
    rating: str  # "positive" | "negative"
    correction: str = ""
    session_id: str = "default"


@app.post("/api/feedback")
def api_feedback(req: FeedbackRequest):
    """Phase 10: submit 👍/👎 (+ optional correction). Never crashes the chat."""
    try:
        sid = req.session_id
        if req.trace_id:
            trace = tracer.get_trace(req.trace_id)
            if trace and trace.get("session_id"):
                sid = trace["session_id"]
        entry = _submit_feedback(req.trace_id or "", sid, req.rating, req.correction or "")
        return {"feedback_id": entry["feedback_id"],
                "category": entry["category"],
                "applied": entry["applied"]}
    except Exception as e:
        # Feedback must never break the app — report cleanly.
        raise HTTPException(status_code=500, detail=f"Feedback failed: {e}")


@app.get("/api/feedback/stats")
def api_feedback_stats():
    """Phase 10: feedback analytics."""
    return feedback.get_stats()


@app.get("/api/feedback/recent")
def api_feedback_recent(limit: int = 20):
    """Phase 10: recent feedback entries."""
    return {"feedback": feedback.get_recent(limit=limit)}


# --------------------------------------------------------------------------- #
# Level 1 — Admin CRUD. These are WRITE endpoints for the human admin panel;
# they deliberately bypass the agent's read-only SQL restriction (the AGENT
# can only read; the ADMIN can write). NOTE: add authentication in production —
# these endpoints are unauthenticated for now.
# --------------------------------------------------------------------------- #
class AdminRow(BaseModel):
    data: dict


@app.get("/api/admin/{table}")
def admin_list_rows(table: str):
    try:
        return {
            "table": table,
            "columns": db.ADMIN_TABLES[table],
            "key": db._admin_key(table),
            "rows": db.admin_list(table),
        }
    except db.UnsafeQueryError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/admin/{table}")
def admin_create_row(table: str, row: AdminRow):
    try:
        result = db.admin_insert(table, row.data)
        print(f"[ADMIN] insert into {table}: {result}")
        return result
    except db.UnsafeQueryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insert failed: {e}")


@app.put("/api/admin/{table}/{row_id}")
def admin_update_row(table: str, row_id: str, row: AdminRow):
    try:
        result = db.admin_update(table, row_id, row.data)
        print(f"[ADMIN] update {table}#{row_id}: {result}")
        return result
    except db.UnsafeQueryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {e}")


@app.delete("/api/admin/{table}/{row_id}")
def admin_delete_row(table: str, row_id: str):
    try:
        result = db.admin_delete(table, row_id)
        print(f"[ADMIN] delete {table}#{row_id}: {result}")
        return result
    except db.UnsafeQueryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


# --------------------------------------------------------------------------- #
# WhatsApp channel (Twilio). Public endpoint — validated by Twilio signature,
# not JWT. Runs incoming messages through the SAME pipeline as web chat.
# --------------------------------------------------------------------------- #
_WA_PENDING: dict[str, str] = {}  # phone -> approval_id awaiting APPROVE/REJECT


@app.post("/api/whatsapp")
async def whatsapp_webhook(request: Request):
    # Parse Twilio's urlencoded body without needing python-multipart.
    from urllib.parse import parse_qs

    raw = (await request.body()).decode("utf-8", "replace")
    params = {k: v[0] for k, v in parse_qs(raw).items()}

    # Security: verify the request genuinely came from Twilio.
    if not whatsapp.validate_signature(
        str(request.url), params, request.headers.get("X-Twilio-Signature")
    ):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature.")

    if not whatsapp.is_configured():
        return JSONResponse(
            {"detail": "WhatsApp not configured. Set TWILIO_ACCOUNT_SID, "
                       "TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER in .env"}
        )

    from_number = params.get("From", "").replace("whatsapp:", "").strip()
    body = (params.get("Body") or "").strip()
    if not from_number or not body:
        return JSONResponse({"ok": True})

    print(f"[WHATSAPP] incoming from {from_number}: {body[:60]}")
    session = f"wa:{from_number}"

    try:
        # Approval decision via text?
        decision = body.strip().upper()
        if decision in ("APPROVE", "REJECT") and _WA_PENDING.get(from_number):
            aid = _WA_PENDING.pop(from_number)
            try:
                if decision == "APPROVE":
                    result = approval.approve(aid)
                else:
                    entry = approval.reject(aid)
                    result = f"Cancelled — the {entry.action.replace('_', ' ')} was not executed."
            except approval.ApprovalNotFound:
                result = "That request has expired or was already handled."
            whatsapp.send_reply(from_number, whatsapp.to_plain(result))
            return JSONResponse({"ok": True})

        # Normal message -> same pipeline as web chat.
        reply, pending, _trace_id, files = await run_routed(body, session)
        text = whatsapp.to_plain(reply)
        for f in files:  # WhatsApp: send file links (public URL)
            text += f"\n\n{f['type'].upper()}: {PUBLIC_BASE_URL}{f['url']}"
        if pending:
            _WA_PENDING[from_number] = pending["approval_id"]
            d = pending.get("details", {})
            text += (
                f"\n\n[APPROVAL NEEDED] Send email to {d.get('to', '')}?\n"
                "Reply APPROVE to send, or REJECT to cancel."
            )
        whatsapp.send_reply(from_number, text)
    except Exception as e:
        print(f"[WHATSAPP] processing error: {e}")
        whatsapp.send_reply(from_number, "Sorry, something went wrong. Please try again.")
    return JSONResponse({"ok": True})


@app.post("/api/approve", response_model=ChatResponse)
async def approve_action(req: ApprovalRequest):
    """Execute a pending high-risk action after explicit human approval."""
    try:
        result = approval.approve(req.approval_id)
        return ChatResponse(reply=result)
    except approval.ApprovalNotFound:
        raise HTTPException(
            status_code=404,
            detail="This approval is unknown, already decided, or has expired.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval execution failed: {e}")


@app.post("/api/reject", response_model=ChatResponse)
async def reject_action(req: ApprovalRequest):
    """Cancel a pending high-risk action. Nothing executes."""
    try:
        entry = approval.reject(req.approval_id)
        return ChatResponse(
            reply=f"Action cancelled — the {entry.action.replace('_', ' ')} was not executed."
        )
    except approval.ApprovalNotFound:
        raise HTTPException(
            status_code=404,
            detail="This approval is unknown, already decided, or has expired.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {e}")


if __name__ == "__main__":
    # Local / platform run. Render (and most hosts) inject PORT — honour it.
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
