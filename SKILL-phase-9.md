---
name: phase-9-observability-tracing
description: "Build Phase 9 of the AI Agent System — add a tracing and observability layer so every request, every agent call, every tool execution, every token spent, and every decision is logged in a structured, queryable trace. This is the 'X-ray vision' for debugging, performance monitoring, and cost tracking. Use this only after Phase 8 (smart router) is complete and verified. Without observability, debugging a multi-agent system is guessing in the dark."
---

# Phase 9 — Observability & Tracing

## Prerequisite (do not skip)

Phase 0-8 must already be complete and verified. Phase 9 extends the SAME project. Do NOT rebuild anything from scratch.

---

## Goal (read this first)

Right now the only visibility into what the system does is scattered `print()` logs in the terminal — [PLAN], [TOOL CALLED], [QA], [RETRY], [ROUTER], etc. These are useful but:
- They scroll away and are lost when the terminal closes.
- There is no way to see the FULL chain of a single request (router → planner → step 1 → tool → step 2 → QA → response) in one connected view.
- There is no way to query past requests ("show me all requests that failed last hour" or "which tool is slowest?").
- There is no way to track cost over time.

In Phase 9, add a structured tracing system:

> Every request gets a unique trace. Within that trace, every step (routing, planning, tool calls, QA, approval, response) is recorded as a span with timing, input/output, token count, and status. Traces are stored persistently and can be queried/viewed.

**Phase 9 is complete when:** every request produces a structured trace with connected spans, traces are stored persistently, and there is a way to view/query them (a simple API endpoint or dashboard page).

---

## Architecture decision — lightweight custom tracer (NOT Langfuse cloud)

Do NOT set up Langfuse cloud or any external SaaS in Phase 9. Instead, build a lightweight custom tracing system that:
- Stores traces locally (JSON files or SQLite — use the existing SQLite from Phase 4).
- Provides a simple API endpoint to query traces.
- Provides a simple frontend page to view traces (a basic trace viewer).
- Can be upgraded to Langfuse or any external system later by swapping the storage backend.

This keeps Phase 9 self-contained, free, and working without external dependencies.

---

## What a trace looks like

Each request produces ONE trace. A trace contains multiple spans (one per step). Example:

```
TRACE: abc-123
├── timestamp: 2025-01-15T10:30:00Z
├── session_id: sess-456
├── user_message: "get June sales and make a PDF report"
├── route: COMPLEX
├── total_duration_ms: 8500
├── total_tokens: 1340
├── status: success
│
├── SPAN: router
│   ├── duration_ms: 120
│   ├── input: "get June sales and make a PDF report"
│   ├── output: "COMPLEX"
│   └── tokens: 85
│
├── SPAN: planner
│   ├── duration_ms: 1200
│   ├── input: "get June sales and make a PDF report"
│   ├── output: ["1. query June sales", "2. generate PDF report"]
│   └── tokens: 320
│
├── SPAN: tool_call (query_sales)
│   ├── duration_ms: 45
│   ├── input: { month: "June" }
│   ├── output: { sales: 45000 }
│   ├── tokens: 0 (deterministic tool)
│   └── status: success
│
├── SPAN: tool_call (generate_report)
│   ├── duration_ms: 800
│   ├── input: { title: "June Sales", data: ... }
│   ├── output: { file: "june-report.pdf" }
│   ├── tokens: 0
│   └── status: success
│
├── SPAN: qa_review
│   ├── duration_ms: 15
│   ├── checks_passed: 4
│   ├── checks_failed: 0
│   └── status: PASS
│
└── SPAN: response
    ├── duration_ms: 50
    ├── output: "Here is your June sales report..."
    └── status: delivered
```

---

## What to build

### Part 1 — Tracer module (`backend/tracer.py`)

Build a clean tracing module with these core functions:

```
start_trace(request_message, session_id) -> trace_id
    Creates a new trace, records timestamp, message, session.

start_span(trace_id, span_name, input_data) -> span_id
    Creates a span within a trace, records start time and input.

end_span(span_id, output_data, tokens=0, status="success", metadata={})
    Closes a span, records end time, duration, output, tokens, status.

end_trace(trace_id, final_response, total_tokens, status="success")
    Closes the trace, records total duration, response, status.

get_trace(trace_id) -> dict
    Returns the full trace with all spans.

list_traces(limit=50, status=None, since=None) -> list
    Returns recent traces, optionally filtered by status or time.

get_stats() -> dict
    Returns aggregate stats: total requests, avg duration, total tokens,
    error rate, tokens by route (simple vs complex), slowest tools, etc.
```

Storage: use a SQLite table (reuse the existing `company.db` or create `traces.db`). Two tables:
- `traces` (trace_id, session_id, message, route, total_duration_ms, total_tokens, status, response, created_at)
- `spans` (span_id, trace_id, name, input, output, duration_ms, tokens, status, metadata, created_at)

Keep inputs/outputs as JSON text in the columns. Index on trace_id and created_at.

### Part 2 — Instrument the existing code

Add tracing calls into the existing flow WITHOUT changing its logic. The tracer is an observer, not a participant — it should never affect the outcome of a request.

Where to add spans:
- **Router classification** → span "router" (input: message, output: simple/complex, tokens used).
- **Planner** → span "planner" (input: message, output: plan steps, tokens).
- **Each tool call** → span "tool:{tool_name}" (input: tool args, output: tool result, duration).
- **Each retry attempt** → span "retry:{tool_name}" (input: attempt number, output: success/fail).
- **QA review** → span "qa" (input: draft, output: pass/fail, findings).
- **Approval** → span "approval" (input: action, output: pending/approved/rejected).
- **Fast-track response** → span "fast_track" (for simple requests).
- **Final response assembly** → span "response".

Important rules:
- If tracing fails (DB write error, etc.), it must NEVER crash the request. Wrap all tracing calls in try/except and silently log the tracing error. The request must succeed even if tracing is broken.
- Do not log sensitive data (full API keys, passwords) in trace inputs/outputs. PII that was redacted by QA should stay redacted in traces too.
- Keep trace data reasonably sized — truncate very long inputs/outputs to ~500 chars in the stored trace.

### Part 3 — Trace API endpoints

Add these endpoints to the FastAPI backend:

- `GET /api/traces` — list recent traces (supports `?limit=50&status=success&since=2025-01-15`). Returns a JSON array of trace summaries.
- `GET /api/traces/{trace_id}` — get one full trace with all its spans. Returns the full trace dict.
- `GET /api/stats` — get aggregate stats (total requests, avg duration, total tokens, error rate, tokens by route, top slowest tools). Returns a JSON stats object.

These endpoints are for debugging and monitoring — they do NOT need auth in Phase 9 (auth is a later concern).

### Part 4 — Simple trace viewer (frontend page)

Add a minimal dashboard page at `/dashboard` (or `/traces`) in the Next.js frontend. Keep it simple but functional:

- A list of recent traces (timestamp, message preview, route, duration, status, tokens). Click to expand.
- Expanded view shows the full span chain: each span's name, duration, status, input/output (truncated).
- Color-code: green for success, red for failure, yellow for warning/retry.
- A stats summary at the top: total requests today, avg response time, total tokens used, error rate.
- Auto-refresh every 30 seconds (or a manual refresh button).
- Keep the design consistent with the existing colorful UI theme.

This does NOT need to be a fancy Grafana-level dashboard. A clean, readable page that lets you see what happened and spot problems is enough.

### Part 5 — Add trace_id to chat responses

Include the trace_id in the /api/chat response so it can be correlated:
```json
{
  "reply": "...",
  "trace_id": "abc-123"
}
```
The frontend can optionally show this as a small clickable link (e.g. "trace: abc-123" at the bottom of the AI message) that opens the trace detail. This is optional but very useful for debugging.

---

## Logging

Keep the existing terminal logs ([PLAN], [TOOL CALLED], [QA], etc.) — they are still useful for real-time monitoring. The tracer ADDS structured persistence on top; it does not replace the terminal logs.

Add one new log per request:
- `[TRACE] abc-123 completed — 8500ms, 1340 tokens, status: success`
- `[TRACE] def-456 completed — 350ms, 119 tokens, status: success (fast-track)`

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- Tracer module with start/end trace/span functions.
- SQLite storage for traces and spans.
- Instrumentation of all existing steps (router, planner, tools, QA, approval, response).
- Three API endpoints (/api/traces, /api/traces/{id}, /api/stats).
- Simple trace viewer frontend page.
- trace_id in chat responses.
- Terminal log per completed trace.

**OUT of scope (DO NOT build):**
- No Langfuse cloud or any external SaaS.
- No feedback loop (Phase 10).
- No alerting based on traces (later enhancement).
- No auth on trace endpoints (later).
- No new tools, agents, or business logic changes.

---

## "Done" checklist (Phase 9 is complete when ALL are true)

- [ ] **Every request produces a trace:** both simple (fast-track) and complex requests create a trace with spans in the database.
- [ ] **Spans cover all steps:** router, planner, tool calls, QA, approval, response — each has a span with timing, input/output, tokens, status.
- [ ] **Traces are persistent:** traces survive a backend restart (stored in SQLite).
- [ ] **GET /api/traces returns recent traces** with filtering support.
- [ ] **GET /api/traces/{id} returns the full trace** with all spans.
- [ ] **GET /api/stats returns aggregate stats** (total requests, avg duration, total tokens, error rate).
- [ ] **Trace viewer page exists** at /dashboard (or /traces) and shows a readable list of traces with expandable span details.
- [ ] **trace_id is in the chat response** JSON.
- [ ] **Tracing never crashes a request** — if the tracer fails, the request still succeeds.
- [ ] **Sensitive data is not leaked** in traces — PII stays redacted, no raw API keys.
- [ ] All Phase 2-8 features still work. Frontend chat UI unchanged (dashboard is a separate page).
- [ ] Terminal still shows existing logs + new [TRACE] completion log.

When every box is checked, STOP. Phase 9 is done. Do not start Phase 10 in this same task.

---

## How to verify quickly

1. Run backend and frontend.
2. Send a few requests (simple and complex).
3. Open `/dashboard` in the browser → see the traces listed with timing and token counts.
4. Click a complex trace → see the full span chain (router → planner → tool → QA → response).
5. Hit `GET /api/stats` → see aggregate numbers.
6. Restart the backend → traces are still there (persistent).
7. Send a request that triggers a retry (use force_fail) → see the retry span in the trace.

If every request is traced, spans are complete, the dashboard shows them, and nothing crashes — Phase 9 is done.

---

## Notes for later

- Phase 10 (final phase) adds the feedback loop — user corrections improve future responses.
- After Phase 10, the tracer can be upgraded to export to Langfuse, Datadog, or any external observability platform by adding an exporter that reads from the SQLite traces and pushes to the external API. The trace format is already compatible.
- Alerting rules can be added later: "if error rate > 10% in last hour, send alert" — these query the same traces/stats.
