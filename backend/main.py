import os
import re
from pathlib import Path

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import approval
import database as db
import dead_letter
import qa
import resilience
import router
from emailing import draft_email as draft_email_impl, send_email as send_email_impl
from memory import PreferenceStore, ShortTermMemory
from reporting import REPORTS_DIR, generate_report as generate_report_impl

load_dotenv()

app = FastAPI(title="AI Agent System — Phase 8")

short_term = ShortTermMemory()
preferences = PreferenceStore(Path(__file__).parent / "preferences.json")

# Real database (Phase 4). Seed on startup so there is real data to query.
# Seeding is idempotent and uses a read-write connection; the query TOOL only
# ever touches the read-only path.
db.seed()

# Base URL used to turn a generated report path into a downloadable link.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated PDF reports so the reply can link to a downloadable file.
REPORTS_DIR.mkdir(exist_ok=True)
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")


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
    "pending": [],  # approval.Pending entries created during this request
}

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


def guarded(tool_name: str, fn):
    """Run a tool's real work with retry + backoff, dead-lettering on exhaustion.

    Returns ``(True, result)`` on success or ``(False, user_message)`` on
    failure. Every unrecovered failure is recorded on the request context so
    the Phase 5 QA layer can flag it to the user.
    """
    def _do():
        _maybe_inject_fault(tool_name)
        return fn()

    try:
        return True, resilience.call_with_retry(_do, tool_name=tool_name)
    except resilience.RetryExhausted as e:
        # Transient failure survived all retries -> save it, alert, flag it.
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
    ok, out = guarded("generate_report", lambda: generate_report_impl(title, body))
    if not ok:
        return out
    result = out
    print(f"[TOOL CALLED] generate_report -> {result['filename']}")
    url = f"{PUBLIC_BASE_URL}/reports/{result['filename']}"
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
    ok, out = guarded("draft_email", lambda: draft_email_impl(to, subject, body, attachment))
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
    if send and approval.classify_risk("send_email") == approval.REQUIRES_APPROVAL:
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


sales_agent = Agent(
    name="Worker",
    instructions=(
        "You are a worker agent executing ONE step of a larger plan. Use the "
        "right tool for the step:\n"
        "- Sales figures: use query_sales to read the REAL number from the "
        "database. Never guess.\n"
        "- Report/PDF: use generate_report, putting the real figures from "
        "earlier steps into the body. Return the link it gives you.\n"
        "- Email: use draft_email. It drafts the email; if the user "
        "explicitly asked to SEND it, also set send=true — a human must "
        "approve before anything is actually sent.\n"
        "- Lasting user preference: use save_preference.\n"
        "For reasoning or summarising steps, use the results of earlier steps "
        "and the conversation context provided in the input. "
        "Reply with only the result of this step, briefly."
    ),
    model="gpt-4o-mini",
    tools=[query_sales, generate_report, draft_email, save_preference],
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
        "- The available actions are: read sales data from the database, "
        "generate a PDF report, draft an email (sending requires human "
        "approval and happens after the plan), and save a preference. Plan a "
        "data step BEFORE a report/email step that needs that data. Do not "
        "plan steps needing any other capability (no web search)."
    ),
    model="gpt-4o-mini",
    output_type=Plan,
)

supervisor_agent = Agent(
    name="Supervisor",
    instructions=(
        "You are the supervisor. You are given the user's original request, "
        "conversation context, and the results of the plan steps that were "
        "executed. Combine them into ONE clear, natural final reply to the "
        "user, respecting any known user preferences. Do not mention the "
        "plan, the steps, or other agents."
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
    result = await Runner.run(sales_agent, input=worker_input)
    return str(result.final_output or "")


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
    final = await Runner.run(supervisor_agent, input=supervisor_input)
    return str(final.final_output or "")


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

        plan_result = await Runner.run(
            planner_agent,
            input=f"{memory_context}\n\nNew user request: {message}",
        )
        steps = plan_result.final_output.steps or [message]
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
            result = qa.review(reply, step_results, steps, tool_failures=failures)
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
    memory_context = build_memory_context(session_id)
    result = await Runner.run(
        chat_agent,
        input=f"{memory_context}\n\nUser: {message}",
    )
    reply = qa.pii_only(str(result.final_output or ""))
    short_term.add_turn(session_id, message, reply)
    router.log_cost("simple fast-track", memory_context, message, reply, overhead=100)
    return reply


async def run_routed(message: str, session_id: str) -> tuple[str, dict | None]:
    """Phase 8 entry point: classify first, then fast-track or full pipeline."""
    history = short_term.history(session_id)
    history_text = "\n".join(
        f"User: {t['user']}\nAssistant: {t['assistant']}" for t in history[-6:]
    )
    decision, _reason = await router.classify(message, history_text)
    if decision == router.SIMPLE:
        return await run_fast_track(message, session_id), None
    return await run_supervised(message, session_id)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    pending_approval: dict | None = None  # Phase 7: set when a decision is needed


class ApprovalRequest(BaseModel):
    approval_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not set. Add it to backend/.env",
        )
    try:
        reply, pending = await run_routed(req.message, req.session_id)
        return ChatResponse(reply=reply, pending_approval=pending)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}")


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
