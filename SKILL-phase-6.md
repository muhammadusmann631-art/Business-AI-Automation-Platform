---
name: phase-6-failure-handling
description: "Build Phase 6 of the AI Agent System — add robust failure handling so the system never crashes silently. When a tool or API fails, the system retries with backoff, and if it still fails, queues the task in a dead-letter store and alerts the operator. Use this only after Phase 5 (QA/Reviewer + guardrails) is complete and verified. This is what separates a demo from a production system — graceful failure recovery."
---

# Phase 6 — Failure Handling (retry + dead-letter + alert)

## Prerequisite (do not skip)

Phase 0-5 must already be complete and verified:
- Phase 0: frontend <-> FastAPI <-> OpenAI round trip.
- Phase 1: agent + tool loop.
- Phase 2: Supervisor + Planner.
- Phase 3: Memory (short-term + long-term).
- Phase 4: Real business tools (read-only SQL, PDF, draft email).
- Phase 5: QA/Reviewer guardrails (deterministic checks before output).

Phase 6 extends that SAME backend. Do NOT rebuild anything from scratch.

---

## Goal (read this first)

Right now if a tool fails (database down, OpenAI API timeout, PDF library error, disk full), the system returns a generic 500 error and the user gets nothing useful. The task is lost — nobody knows it failed, nobody retries it, nobody follows up.

In Phase 6, add a failure recovery system:

> When any tool or API call fails, the system retries it automatically with increasing wait times (backoff). If it still fails after retries, the failed task is saved to a dead-letter store (so it is not lost) and an alert is logged/triggered so someone knows to look at it. The user gets a clear, helpful message — not a crash.

That behaviour — "retry automatically, if still failing then save the task and alert, never crash or lose work" — is the ENTIRE goal of Phase 6.

**Phase 6 is complete when:** a deliberately broken tool call is retried automatically, and after max retries the task is saved to a dead-letter store with an alert, and the user gets a clear failure message (not a crash or generic 500).

---

## Three components to build

### Component 1 — Retry with exponential backoff
- When a tool call throws an error or times out, retry it automatically.
- Use exponential backoff: wait 1 second before first retry, 2 seconds before second, 4 seconds before third. Maximum 3 retries (so: try once + 3 retries = 4 total attempts).
- Only retry on transient/recoverable errors (network timeout, temporary DB connection failure, API rate limit). Do NOT retry on permanent errors (invalid query, missing required parameter, authentication failure) — those should fail immediately.
- Log each retry: `[RETRY] attempt 2/4 for <tool_name> after <wait>s — reason: <error>`.

### Component 2 — Dead-letter store
- If a task/tool call fails even after all retries, save it to a dead-letter store so it is NOT lost and can be investigated or replayed later.
- Keep the dead-letter store simple and lightweight for Phase 6: a JSON file on disk (e.g. `backend/dead_letters.json`) is sufficient. Each entry should contain:
  - Timestamp (when it failed).
  - The original user request/message.
  - Which tool/step failed.
  - The error message.
  - How many retries were attempted.
  - The conversation/session id (from Phase 3 memory).
- Log when a task hits the dead-letter store: `[DEAD-LETTER] task saved — tool: <name>, error: <reason>`.
- Do NOT build a full message queue system (RabbitMQ/Redis queue) in Phase 6. A JSON file is enough to prove the pattern. It can be upgraded to a real queue later.

### Component 3 — Alert / notification
- When a task lands in the dead-letter store, trigger an alert so the operator knows.
- For Phase 6, the alert is simply a clearly visible log line: `[ALERT] ⚠️ TOOL FAILURE — <tool_name> failed after 4 attempts. Task saved to dead-letter store. Manual review required.`
- Optionally, also save alerts to a separate lightweight file (e.g. `backend/alerts.json`) so there is a persistent record.
- Do NOT integrate with Slack/email/SMS notifications in Phase 6 — that is a later enhancement. A clear terminal log + optional file is sufficient.

---

## How it fits the existing flow

The existing flow (after Phase 5):
```
Request -> Supervisor -> Planner -> Steps execute (tools) -> QA check -> Return
```

After Phase 6, the step execution part gains resilience:
```
Request -> Supervisor -> Planner -> Steps execute:
  For each step:
    Try tool call
      -> Success: continue
      -> Fail (transient): RETRY with backoff (max 3 retries)
        -> Success after retry: continue (log recovery)
        -> Still failing: save to DEAD-LETTER + log ALERT + mark step as failed
  -> QA check (Phase 5) runs on whatever succeeded
  -> Return response (with warning if any step failed)
```

Important: the retry logic wraps AROUND individual tool calls, not the entire pipeline. If Step 1 (SQL) succeeds but Step 2 (PDF) fails, Step 1's result is kept — only Step 2 is retried/dead-lettered.

---

## Distinguishing transient vs permanent errors

This is important to get right. Build a simple classifier:

**Transient (DO retry):**
- Connection refused / connection timeout / network error.
- Database "too many connections" or temporary lock.
- OpenAI API rate limit (429) or server error (500/502/503).
- File system "disk busy" or temporary write failure.

**Permanent (do NOT retry — fail immediately):**
- Invalid SQL syntax / query validation failure.
- Missing required parameter / invalid input.
- Authentication failure (wrong API key / credentials).
- Permission denied.
- OpenAI API invalid request (400).

If uncertain whether an error is transient or permanent, default to transient (retry). It is better to retry unnecessarily than to lose a recoverable task.

---

## Logging

Print clear logs to the backend terminal:

- `[RETRY] attempt 2/4 for query_sales after 1s — reason: Connection refused` — on each retry.
- `[RETRY] recovered on attempt 3/4 for query_sales` — when a retry succeeds.
- `[DEAD-LETTER] task saved — tool: generate_report, error: disk full, attempts: 4` — when max retries exhausted.
- `[ALERT] ⚠️ TOOL FAILURE — generate_report failed after 4 attempts. Task saved to dead-letter store. Manual review required.` — the alert.
- If all tools succeed without any retry, no extra logs needed (keep it clean for the normal case).

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- Retry with exponential backoff (max 3 retries) on transient errors.
- Dead-letter store (JSON file on disk) for tasks that fail after all retries.
- Alert logging (terminal + optional file) when a task is dead-lettered.
- Transient vs permanent error classification.
- Terminal logs for all retry/failure/alert activity.
- A way to deliberately trigger a failure for testing (e.g. a test endpoint or a flag that makes a tool fail on purpose).

**OUT of scope (DO NOT build — later phases):**
- No human-in-the-loop approval (Phase 7).
- No real email sending (still draft-only, Phase 7).
- No smart router (Phase 8).
- No observability dashboard / Langfuse (Phase 9).
- No Slack/email/SMS alert integrations (later enhancement).
- No full message queue system (RabbitMQ/Redis/Celery). JSON file only.
- No new tools, no new agents, no auth, no multi-tenant.

---

## Build order

### Step 1 — Build the retry wrapper
1. Create a reusable retry function/decorator (e.g. in `backend/retry.py` or `backend/resilience.py`).
2. It should accept: the function to call, max retries (default 3), backoff multiplier, and a way to classify transient vs permanent errors.
3. Test it in isolation with a function that fails N times then succeeds — confirm it retries with backoff and eventually returns success.

### Step 2 — Build the dead-letter store
1. Create a simple module (e.g. `backend/dead_letter.py`) with a `save(entry)` function that appends to a JSON file.
2. Each entry has: timestamp, request, tool, error, attempts, session_id.
3. Test it in isolation — call save() and confirm the JSON file is created/appended correctly.

### Step 3 — Wire into the step execution
1. Wrap each tool call in the existing Supervisor/step-execution flow with the retry wrapper.
2. On max-retries-exhausted: save to dead-letter, log the alert, mark the step as failed.
3. The QA layer (Phase 5) will see the failed step and handle it (warning to user).

### Step 4 — Add a test/debug mechanism
1. Add a simple way to force a tool to fail for testing purposes (e.g. a query parameter like `?force_fail=sql` on the /api/chat endpoint, or a special message like "TEST: force sql failure"). This is for verification only.
2. This makes it easy to prove the retry -> dead-letter -> alert chain without actually breaking the database.

### Step 5 — Verify (see checklist below)

---

## "Done" checklist (Phase 6 is complete when ALL are true)

- [ ] **Retry works:** a transient tool failure is retried automatically with backoff, and the terminal shows `[RETRY] attempt N/4 ...` logs with increasing wait times.
- [ ] **Recovery works:** if a retry succeeds, the system recovers and returns a good result. Terminal shows `[RETRY] recovered on attempt N`.
- [ ] **Dead-letter works:** after max retries (all fail), the task is saved to a dead-letter JSON file with all required fields (timestamp, request, tool, error, attempts, session_id).
- [ ] **Alert fires:** when a task is dead-lettered, the terminal shows the `[ALERT] ⚠️ TOOL FAILURE ...` message.
- [ ] **User gets a clear message:** when a tool fails permanently, the user gets a helpful response (not a raw 500 or crash), with a warning that part of the request could not be completed.
- [ ] **Permanent errors are not retried:** an invalid/permanent error fails immediately without retrying (no retry logs for that call).
- [ ] **Normal requests are unaffected:** when everything works fine, there are no extra retry/dead-letter logs — the system behaves exactly as before.
- [ ] **Test mechanism exists:** there is a way to deliberately trigger a failure to verify the retry -> dead-letter -> alert chain.
- [ ] Phase 5 QA still works. Phase 4 tools still work. Phase 3 memory still works. Phase 2 Planner still works. Frontend unchanged.
- [ ] Errors never crash the system — every failure path ends in a clean user-facing message.

When every box is checked, STOP. Phase 6 is done. Do not start Phase 7 in this same task.

---

## How to verify quickly

1. Run backend and frontend.
2. **Normal request:** "what were the sales in June?" → works as before, no retry logs. ✅
3. **Forced transient failure + recovery:** trigger a fake transient failure (using the test mechanism) that fails twice then succeeds → terminal shows `[RETRY] attempt 2/4`, `[RETRY] attempt 3/4`, `[RETRY] recovered on attempt 3/4`, and the user gets a correct answer.
4. **Forced permanent failure:** trigger a failure that exhausts all retries → terminal shows all retry attempts, then `[DEAD-LETTER] task saved`, then `[ALERT] ⚠️ ...`. Check the dead_letters.json file — the entry should be there with all fields. User gets a clear warning message, not a crash.
5. **Permanent error (no retry):** send an invalid query that should fail immediately → no retry logs, just a clean error response.

If retries fire on transient errors, dead-letter saves on exhaustion, alerts log, and nothing crashes, Phase 6 is done.

---

## Notes for later (do not build now)

- Phase 7 adds **human-in-the-loop approval** — risky actions pause for approval. Dead-letter items could also be surfaced to humans for manual replay.
- Later, the dead-letter JSON file can be upgraded to a proper queue (Redis/RabbitMQ) and alerts can be sent to Slack/email/SMS.
- The retry wrapper is reusable — when new tools are added in future phases, they automatically get retry protection by using the same wrapper.
