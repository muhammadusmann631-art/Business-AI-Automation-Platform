import os
from pathlib import Path

from agents import Agent, Runner, function_tool
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from emailing import draft_email as draft_email_impl
from memory import PreferenceStore, ShortTermMemory
from reporting import REPORTS_DIR, generate_report as generate_report_impl

load_dotenv()

app = FastAPI(title="AI Agent System — Phase 4")

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


@function_tool
def query_sales(month: str) -> str:
    """Look up the REAL sales figure for a given month from the database.

    Runs a read-only SELECT against the real database. Use this whenever the
    user asks about sales numbers. Do not guess figures from memory.

    Args:
        month: The month name in English, e.g. "June".
    """
    print(f"[TOOL CALLED] sql read-only: sales for {month}")
    try:
        rows = db.query_sales(month)
    except db.UnsafeQueryError as e:
        return f"Query rejected (read-only): {e}"
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
    result = generate_report_impl(title, body)
    print(f"[TOOL CALLED] generate_report -> {result['filename']}")
    url = f"{PUBLIC_BASE_URL}/reports/{result['filename']}"
    return f"PDF report created: {url} (saved at {result['path']})"


@function_tool
def draft_email(to: str, subject: str, body: str, attachment: str = "") -> str:
    """Compose an email DRAFT. Does NOT send anything (draft-only in Phase 4).

    Use this when the user asks to email/draft a message. Returns the draft
    for the user to review; sending is deliberately not available yet.

    Args:
        to: Recipient email address.
        subject: Subject line.
        body: Email body text.
        attachment: Optional report filename/link to reference.
    """
    draft = draft_email_impl(to, subject, body, attachment)
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
    preferences.save(key, value)
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
        "- Email: use draft_email. This only drafts — it never sends.\n"
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
        "generate a PDF report, draft an email (draft only, never sent), and "
        "save a preference. Plan a data step BEFORE a report/email step that "
        "needs that data. Do not plan steps needing any other capability "
        "(no web search, no real sending)."
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


async def run_supervised(message: str, session_id: str) -> str:
    """Supervisor flow: recall memory, plan, execute steps in order, combine."""
    memory_context = build_memory_context(session_id)


    plan_result = await Runner.run(
        planner_agent,
        input=f"{memory_context}\n\nNew user request: {message}",
    )
    steps = plan_result.final_output.steps or [message]
    print("[PLAN] " + "  ".join(f"{i}. {s}" for i, s in enumerate(steps, 1)))

    step_results: list[str] = []
    for i, step in enumerate(steps, 1):
        print(f"[STEP {i}/{len(steps)}] {step}")
        context = "\n".join(
            f"Result of step {j}: {r}" for j, r in enumerate(step_results, 1)
        )
        worker_input = (
            f"{memory_context}\n"
            f"User request: {message}\n"
            f"{context}\n"
            f"Your step to execute now: {step}"
        )
        result = await Runner.run(sales_agent, input=worker_input)
        step_results.append(str(result.final_output or ""))

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
    reply = str(final.final_output or "")
    short_term.add_turn(session_id, message, reply)
    return reply


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str


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
        reply = await run_supervised(req.message, req.session_id)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}")
