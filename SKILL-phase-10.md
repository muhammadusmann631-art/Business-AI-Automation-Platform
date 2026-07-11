---
name: phase-10-feedback-loop
description: "Build Phase 10 (FINAL phase) of the AI Agent System — add a feedback loop so user corrections and ratings improve future responses. When a user says 'this is wrong', 'use blue graphs', or rates a response, that feedback is stored, analyzed, and applied to make the next similar request better. Use this only after Phase 9 (observability/tracing) is complete and verified. This is the final piece that makes the system continuously self-improving — the difference between a static tool and an intelligent system."
---

# Phase 10 — Feedback Loop (continuous improvement)

## Prerequisite (do not skip)

Phase 0-9 must already be complete and verified. Phase 10 extends the SAME project. Do NOT rebuild anything from scratch. This is the FINAL core phase.

---

## Goal (read this first)

Right now the system does not learn from its mistakes. If it gives a wrong answer and the user corrects it, the same mistake can happen again next time. If the user always wants a certain style or format, they have to repeat it every time (Phase 3 preferences help, but only for explicit "always do X" statements — not for implicit patterns).

In Phase 10, close the loop:

> When a user corrects a response, rates it (thumbs up/down), or provides feedback, that feedback is stored, linked to the original trace (Phase 9), analyzed for patterns, and used to improve future responses — either by updating preferences (Phase 3), adjusting prompts, or flagging recurring issues.

**Phase 10 is complete when:** a user correction on one response is remembered and applied to a similar future request, AND a simple feedback analytics view shows patterns (most common corrections, average rating, improvement over time).

---

## Three parts of the feedback loop

### Part 1 — Feedback collection (user input)

**Frontend changes (minimal):**
- Below each AI response, add two small buttons: **👍** (good) and **👎** (bad).
- When 👎 is clicked, show a small text input: "What was wrong? (optional)" — the user can type a correction or leave it blank.
- When 👍 is clicked, record it silently (no extra input needed).
- Also detect **inline corrections** in chat: if the user's message starts with patterns like "no,", "that's wrong", "actually...", "correction:", "instead...", treat it as feedback on the previous response.

**What gets stored per feedback:**
- `feedback_id` (unique).
- `trace_id` (from Phase 9 — links feedback to the exact request/trace).
- `session_id`.
- `rating`: "positive" or "negative".
- `user_correction`: the text the user typed (if any).
- `original_response`: what the system said (the response being rated).
- `original_request`: what the user asked.
- `timestamp`.

### Part 2 — Feedback storage and analysis (`backend/feedback.py`)

**Storage:**
- Use SQLite (same database as traces, or a separate `feedback.db`). One table:
  - `feedback` (feedback_id, trace_id, session_id, rating, user_correction, original_request, original_response, category, applied, timestamp).
- `category` is auto-detected (see below).
- `applied` tracks whether this feedback has been acted on (default: false).

**Auto-categorization:**
When feedback comes in, try to categorize it automatically:
- **"data_error"** — user says the number/data was wrong ("that's not 45000, it's 42000").
- **"format_preference"** — user wants a different style/format ("make it shorter", "use bullet points", "graphs should be blue").
- **"missing_info"** — response was incomplete ("you forgot to include December").
- **"wrong_tool"** — system used the wrong approach ("don't make a PDF, just tell me the number").
- **"tone"** — user wants a different tone ("be more formal", "too wordy").
- **"other"** — does not fit above categories.

Use simple keyword matching for categorization — NOT an LLM call. Keep it deterministic and fast.

**Analysis functions:**
- `get_feedback_stats()` → total feedback, positive %, negative %, breakdown by category, most common corrections.
- `get_recent_feedback(limit=20)` → latest feedback entries.
- `get_feedback_for_trace(trace_id)` → feedback linked to a specific trace.
- `get_improvement_suggestions()` → based on patterns in negative feedback, suggest what to improve (e.g. "5 users said data was wrong for month queries — check SQL tool accuracy").

### Part 3 — Applying feedback (the actual improvement)

This is the most important part. Feedback is useless if it is only stored and never applied. Three mechanisms:

**Mechanism A — Preference auto-extraction:**
- When a format_preference feedback is detected (e.g. "use bullet points", "graphs blue"), automatically save it as a long-term preference (Phase 3 memory).
- Next time, the system applies it without the user repeating.
- Log: `[FEEDBACK] auto-saved preference: "use bullet points"`.

**Mechanism B — Context injection:**
- For each new request, check if there is relevant past negative feedback (same category of request, same type of question).
- If found, inject a brief context note into the Supervisor's prompt: "Note: a similar past request received this correction: [user_correction]. Consider this when responding."
- This is a lightweight, non-destructive way to improve — it does not change the system's code, just adds context.
- Limit to the 3 most relevant past corrections to avoid prompt bloat.
- Log: `[FEEDBACK] injecting 2 past corrections as context`.

**Mechanism C — Flagging for manual review:**
- If a particular type of request gets 3+ negative feedbacks, flag it in the analytics: "⚠️ Recurring issue: [category] on [request type] — manual review recommended."
- This surfaces systematic problems that simple auto-fixes cannot solve (e.g. "the SQL tool keeps returning wrong data for quarterly totals" — that needs a code fix, not a prompt tweak).
- Log: `[FEEDBACK] ⚠️ recurring issue flagged: data_error on quarterly queries (4 negatives)`.

---

## API endpoints

Add these to the FastAPI backend:

- `POST /api/feedback` — submit feedback. Accepts: `{ "trace_id": "...", "rating": "positive"|"negative", "correction": "optional text" }`. Returns: `{ "feedback_id": "...", "category": "...", "applied": true|false }`.
- `GET /api/feedback/stats` — get feedback analytics (total, positive %, categories, common corrections, flagged recurring issues).
- `GET /api/feedback/recent?limit=20` — get recent feedback entries.

---

## Frontend changes

### Chat UI additions (minimal):
- 👍 / 👎 buttons below each AI message. Small, unobtrusive, consistent with the existing design.
- On 👎 click: a small inline text input appears for optional correction. Submit button to send.
- On 👍 click: send positive feedback silently, show a brief "Thanks!" flash.
- Inline correction detection: if the user's chat message matches correction patterns, automatically submit as negative feedback linked to the previous trace.

### Dashboard addition (extend Phase 9 dashboard):
- Add a "Feedback" section/tab to the existing /dashboard page.
- Show: feedback stats (total, positive %, negative %, by category), recent feedback list, flagged recurring issues.
- Keep it simple and consistent with the trace viewer design.

---

## How it fits the existing flow

The flow gains two new touchpoints:

**After response (collection):**
```
... -> Response delivered to user
  -> User clicks 👍/👎 or types a correction
  -> POST /api/feedback -> stored + categorized + auto-applied if possible
```

**Before response (application):**
```
Request comes in -> Router classifies
  -> [FEEDBACK] check for relevant past corrections
  -> Inject relevant corrections into Supervisor context
  -> ... normal pipeline continues ...
```

The feedback injection happens AFTER the router but BEFORE the Planner/Supervisor, so it influences the plan and response without changing the pipeline structure.

---

## Logging

- `[FEEDBACK] received: negative — category: format_preference — "use bullet points"` — on feedback submission.
- `[FEEDBACK] received: positive` — on positive feedback.
- `[FEEDBACK] auto-saved preference: "use bullet points"` — when a correction is saved as a preference.
- `[FEEDBACK] injecting 2 past corrections as context` — when past feedback is used for a new request.
- `[FEEDBACK] ⚠️ recurring issue flagged: data_error on monthly queries (3+ negatives)` — when a pattern is detected.

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- 👍/👎 buttons on AI messages in the chat UI.
- Optional correction text input on 👎.
- Inline correction detection from chat messages.
- Feedback storage in SQLite with auto-categorization.
- Three application mechanisms (preference extraction, context injection, recurring issue flagging).
- API endpoints for feedback submission and analytics.
- Feedback section on the dashboard.
- Terminal logs for feedback activity.

**OUT of scope (these are post-Phase-10 enhancements):**
- No automatic prompt rewriting or fine-tuning.
- No A/B testing of responses.
- No feedback-based model selection.
- No user-facing "improvement report" emails.
- No new tools, agents, or business logic changes.
- No auth on feedback endpoints (later).

---

## "Done" checklist (Phase 10 — FINAL — is complete when ALL are true)

- [ ] **👍/👎 buttons appear** below every AI message in the chat UI.
- [ ] **Positive feedback is recorded:** clicking 👍 stores a positive feedback entry linked to the trace_id.
- [ ] **Negative feedback with correction is recorded:** clicking 👎 + typing a correction stores it with auto-detected category.
- [ ] **Inline corrections are detected:** typing "no, that's wrong, it should be 42000" is auto-detected as feedback on the previous response.
- [ ] **Preference auto-extraction works:** a format correction (e.g. "use bullet points") is auto-saved as a preference (Phase 3) and applied to future responses.
- [ ] **Context injection works:** a past correction is injected into the Supervisor's context for a similar future request, and the response reflects the correction. Terminal shows `[FEEDBACK] injecting...`.
- [ ] **Recurring issue flagging works:** 3+ negative feedbacks of the same category trigger a flag in the analytics.
- [ ] **POST /api/feedback** accepts and stores feedback correctly.
- [ ] **GET /api/feedback/stats** returns meaningful analytics.
- [ ] **Dashboard shows feedback** section with stats, recent entries, and flagged issues.
- [ ] All Phase 2-9 features still work. Chat UI still works (buttons are an addition, not a replacement).
- [ ] Errors handled cleanly — feedback submission failure never crashes the chat.

When every box is checked, STOP. **Phase 10 is the final core phase. The AI Agent System's core is COMPLETE.**

---

## How to verify quickly

1. Run backend and frontend.
2. Send a request: "what were the sales in June?" → get a response.
3. Click 👎 → type "the format was too long, use one line only" → submit.
4. Check: terminal shows `[FEEDBACK] received: negative — category: format_preference`.
5. Send a SIMILAR request: "what were the sales in December?" → the response should be shorter/one-line (context injection applied). Terminal shows `[FEEDBACK] injecting 1 past correction`.
6. Click 👍 on a good response → terminal shows `[FEEDBACK] received: positive`.
7. Open /dashboard → Feedback section shows the entries, stats, and categories.
8. Submit 3+ negative feedbacks of the same type → a recurring issue flag appears.

If feedback is collected, stored, categorized, applied to future requests, and visible on the dashboard — **Phase 10 is done and the core system is COMPLETE.**

---

## 🎉 What you have built (Phase 0-10 complete system)

After Phase 10, you have a complete, professional AI Agent System:

- **Entry**: multi-channel ready (web app, API).
- **Smart Router**: simple requests are fast-tracked; complex requests use the full pipeline. Cost optimized.
- **Brain**: Supervisor understands requests, Planner breaks them into steps, steps execute in order.
- **Memory**: remembers conversations (short-term) and preferences (long-term).
- **Real Tools**: read-only SQL, PDF reports, email (draft + send with approval).
- **Quality Gate**: every output is checked (completeness, data sanity, PII redaction, business rules) before reaching the user.
- **Failure Resilience**: transient failures are retried with backoff; permanent failures are dead-lettered with alerts. Nothing crashes, nothing is lost.
- **Human Approval**: risky actions pause for explicit human approve/reject.
- **Observability**: every request is traced with full span details, stored persistently, viewable in a dashboard.
- **Continuous Improvement**: user feedback is collected, categorized, and applied to improve future responses.

This is a production-grade foundation. From here, you can add: multi-tenant isolation, RBAC, more tools (Excel, web search, CRM), Slack/Teams integration, async job queues, and scale to enterprise — all by extending what already works.
