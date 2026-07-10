---
name: phase-8-smart-router
description: "Build Phase 8 of the AI Agent System — add a smart router that classifies incoming requests as 'simple' or 'complex' BEFORE they enter the full pipeline. Simple requests (greetings, quick facts, one-line answers) get a fast, cheap direct response. Complex requests (multi-step, data needed, reports, emails) go through the full Supervisor/Planner/tools pipeline. This dramatically reduces cost and latency for easy questions. Use this only after Phase 7 (human approval) is complete and verified."
---

# Phase 8 — Smart Router (cost + speed optimization)

## Prerequisite (do not skip)

Phase 0-7 must already be complete and verified:
- Phase 0: frontend <-> FastAPI <-> OpenAI round trip.
- Phase 1: agent + tool loop.
- Phase 2: Supervisor + Planner.
- Phase 3: Memory (short-term + long-term).
- Phase 4: Real business tools (read-only SQL, PDF, draft email).
- Phase 5: QA/Reviewer guardrails.
- Phase 6: Failure handling (retry, dead-letter, alert).
- Phase 7: Human-in-the-loop approval.

Phase 8 extends the SAME project. Do NOT rebuild anything from scratch.

---

## Goal (read this first)

Right now EVERY request — even "hi" or "what time is it?" — goes through the full heavy pipeline: Supervisor → Planner → step breakdown → tool execution → QA → response. This is wasteful:
- A simple "hello" triggers planning, step execution, QA checks — burning tokens and adding latency for no reason.
- The full pipeline costs ~5-10x more tokens than a direct answer for a simple question.

In Phase 8, add a smart router at the ENTRY point:

> Before entering the pipeline, a fast, cheap classification decides: is this request SIMPLE (direct answer) or COMPLEX (needs the full pipeline)? Simple requests get a quick, direct response using a lightweight model call. Complex requests go through the full Supervisor/Planner/tools pipeline as before.

**Phase 8 is complete when:** simple questions ("hi", "what is 2+2?", "what day is today?") get fast direct answers WITHOUT triggering the Planner/tools pipeline, AND complex requests ("get June sales and make a PDF report") still go through the full pipeline correctly.

---

## How the router works

### Classification approach (two options — pick the most appropriate)

**Option A (recommended) — lightweight LLM classification:**
- Use a SINGLE, cheap, fast model call (e.g. gpt-4o-mini with a very short prompt) to classify the request.
- The classifier prompt should be minimal (under 200 tokens), something like:
  "Classify this user request as SIMPLE or COMPLEX. SIMPLE = can be answered directly without any tools, data lookup, file generation, or multi-step work (greetings, general knowledge, quick math, opinions, definitions). COMPLEX = needs database queries, reports, emails, multi-step analysis, or any tool usage. Reply with exactly one word: SIMPLE or COMPLEX."
- This adds one tiny, fast API call but gives accurate classification.

**Option B — keyword/rule-based classification:**
- Check for keywords/patterns that signal complexity: "report", "PDF", "email", "send", "sales data", "analyze", "compare", month names (suggesting data lookup), etc.
- If any complexity signal is found → COMPLEX. Otherwise → SIMPLE.
- Faster (no API call) but less accurate for edge cases.

Either option is acceptable. Option A is more accurate; Option B is cheaper. Choose based on judgment. Both must be clearly implemented in a separate module.

### The two paths

**SIMPLE path (fast track):**
1. Router classifies as SIMPLE.
2. Make ONE direct OpenAI call (not through the Supervisor/Planner) with the user's message + conversation history (Phase 3 memory).
3. Run a lightweight QA check (PII redaction only — skip completeness/business-rule checks since no tools ran).
4. Return the response. No [PLAN], no [STEP], no tool calls.
5. Log: `[ROUTER] SIMPLE — fast track`.

**COMPLEX path (full pipeline):**
1. Router classifies as COMPLEX.
2. Everything works exactly as before: Supervisor → Planner → steps → tools → QA → approval if needed → response.
3. Log: `[ROUTER] COMPLEX — full pipeline`.

### Edge case handling
- If the router is UNSURE, default to COMPLEX (better to over-process than to miss a tool-needing request).
- If a request LOOKS simple but mentions data/tools/reports/email, classify as COMPLEX.
- The router should consider conversation history — if previous turns involved complex work and the user says "now summarize that", it is COMPLEX (needs the prior context/data), not SIMPLE.

---

## What to build

### Part 1 — Router module
- Create `backend/router.py`.
- A function `classify(message, conversation_history) -> "simple" | "complex"`.
- Implement your chosen approach (LLM-based or rule-based).
- If LLM-based: use a cheap model (gpt-4o-mini) with a minimal prompt. Cache the classification if the same message is repeated.
- Log the classification decision with reason.

### Part 2 — Fast-track response handler
- Create a direct response function that handles SIMPLE requests:
  - Takes the message + conversation history.
  - Makes ONE direct OpenAI call (no Supervisor, no Planner, no tools).
  - Runs PII-only QA check.
  - Returns in the same `{"reply": ...}` JSON format.
- This is similar to what Phase 0 had, but now with memory (history) and PII protection.

### Part 3 — Wire into /api/chat
- The /api/chat endpoint now does:
  1. Load memory/history (Phase 3).
  2. Call the router to classify.
  3. If SIMPLE → fast-track handler.
  4. If COMPLEX → existing run_supervised() (full pipeline).
  5. Save to history (Phase 3).
  6. Return response.
- The try/except error handling wraps everything as before.

### Part 4 — Cost/token tracking (lightweight)
- Log the approximate token usage for each request: `[COST] simple request — ~200 tokens` vs `[COST] complex request — ~2500 tokens`.
- This does NOT need to be exact or connect to billing. Just a rough count logged to the terminal so the cost savings are visible.
- Optionally: track a running total in memory (reset on restart) and log it periodically.

---

## Logging

- `[ROUTER] SIMPLE — fast track (reason: greeting/general knowledge)` — when classified as simple.
- `[ROUTER] COMPLEX — full pipeline (reason: requires data lookup/report)` — when classified as complex.
- `[ROUTER] UNCERTAIN — defaulting to COMPLEX` — when unsure.
- `[COST] ~200 tokens (simple fast-track)` — after a simple request.
- `[COST] ~2500 tokens (full pipeline)` — after a complex request.
- All existing Phase 2-7 logs still appear for COMPLEX requests (since the full pipeline runs).

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- Router module (classify simple vs complex).
- Fast-track response handler for simple requests.
- PII-only QA on fast-track responses.
- Wiring in /api/chat (router before pipeline).
- Cost/token logging (approximate, terminal only).
- Terminal logs for routing decisions.

**OUT of scope (DO NOT build — later phases):**
- No observability dashboard / Langfuse (Phase 9).
- No feedback loop (Phase 10).
- No semantic caching (later optimization — can be added after Phase 10).
- No new tools, no new agents, no auth, no multi-tenant.
- No billing integration or cost dashboard — just terminal logs.

---

## "Done" checklist (Phase 8 is complete when ALL are true)

- [ ] **Simple requests are fast-tracked:** "hi", "what is 2+2?", "explain what AI is" → `[ROUTER] SIMPLE`, direct response, NO [PLAN]/[STEP]/[TOOL CALLED] logs. Response is noticeably faster.
- [ ] **Complex requests use full pipeline:** "get June sales and make a PDF report" → `[ROUTER] COMPLEX`, full Supervisor/Planner/tools flow with all existing Phase 2-7 behaviour.
- [ ] **Edge cases default to COMPLEX:** ambiguous requests that MIGHT need tools → classified as COMPLEX (safe default).
- [ ] **Context-aware routing:** if previous turns had complex work and user says "summarize that" → COMPLEX (needs prior data), not SIMPLE.
- [ ] **PII still redacted on fast-track:** even simple responses go through PII check.
- [ ] **Memory still works:** fast-track responses use conversation history; follow-up references work.
- [ ] **Cost logging visible:** terminal shows `[COST]` with approximate token counts, and simple requests show significantly fewer tokens than complex ones.
- [ ] **All Phase 2-7 features intact:** Planner, memory, real tools, QA, retry/dead-letter, approval — all still work for complex requests.
- [ ] Frontend unchanged — same JSON contract, same UI.
- [ ] Errors handled cleanly — router failure defaults to COMPLEX (never crashes).

When every box is checked, STOP. Phase 8 is done. Do not start Phase 9 in this same task.

---

## How to verify quickly

1. Run backend and frontend.
2. **Simple test:** type "hi" → fast response, terminal shows `[ROUTER] SIMPLE` and `[COST] ~200 tokens`. NO [PLAN] or [TOOL CALLED] logs.
3. **Complex test:** type "get June sales and make a PDF report" → terminal shows `[ROUTER] COMPLEX`, then the full [PLAN] → [STEP] → [TOOL CALLED] flow. `[COST]` shows higher tokens.
4. **Edge case:** type something ambiguous like "tell me about our sales" → should route COMPLEX (mentions "sales" = likely needs data).
5. **Context test:** after a complex request, type "now summarize that" → should route COMPLEX (needs prior data), not SIMPLE.
6. **Speed difference:** notice that simple requests come back noticeably faster than complex ones.

If simple is fast-tracked, complex uses the full pipeline, edge cases default to complex, and costs are visibly different — Phase 8 is done.

---

## Notes for later (do not build now)

- Phase 9 adds **observability** (Langfuse tracing) — every request, every agent call, every tool, every token is visible in a dashboard. The router classification will also be traced.
- Phase 10 adds the **feedback loop** — user corrections improve future responses.
- After Phase 10, a **semantic cache** can be added: if the same (or very similar) question was asked recently, return the cached answer without any API call at all. This stacks on top of the router for even more cost savings.
- The router classification can be fine-tuned over time based on real usage patterns (which requests actually needed tools vs which didn't).
