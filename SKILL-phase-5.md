---
name: phase-5-reviewer-qa-guardrails
description: "Build Phase 5 of the AI Agent System — add a Reviewer/QA agent and basic guardrails so that every output is validated BEFORE being returned to the user. Use this only after Phase 4 (real business tools: read-only SQL, PDF reports, draft email) is complete and verified. This adds the quality-control layer: checking data accuracy, output completeness, PII redaction, and business-rule compliance. Nothing leaves the system unchecked after this phase."
---

# Phase 5 — Reviewer / QA Agent + Guardrails

## Prerequisite (do not skip)

Phase 0-4 must already be complete and verified:
- Phase 0: frontend <-> FastAPI <-> OpenAI round trip.
- Phase 1: agent + tool loop proven.
- Phase 2: Supervisor + Planner (plan -> ordered steps -> combined reply).
- Phase 3: short-term + long-term memory.
- Phase 4: real read-only SQL, real PDF report, draft-only email — all working through the Supervisor/Planner flow.

Phase 5 extends that SAME backend. Do NOT rebuild anything from scratch.

---

## Goal (read this first)

Right now every output from the tools/agents goes directly to the user without any check. If the SQL returns wrong data, if the PDF is empty, if the email draft has missing fields, or if the response contains sensitive information — nobody catches it.

In Phase 5, add a quality gate:

> Before ANY final response reaches the user, a Reviewer/QA step inspects it. If it passes, the response goes through. If it fails, the system either fixes the problem (retry the failing step) or flags it clearly to the user instead of silently returning bad output.

That behaviour — "check everything before it leaves, catch problems, fix or flag" — is the ENTIRE goal of Phase 5.

**Phase 5 is complete when:** the system catches intentionally bad/incomplete output and either fixes it or flags it, AND good output passes through cleanly without unnecessary blocking.

---

## What the Reviewer/QA checks (the guardrails)

Build these checks as a clear, separate layer (not scattered across random places). The Reviewer runs AFTER the Supervisor has a draft final answer but BEFORE it is returned to the user.

### Check 1 — Output completeness
- Did the plan have steps? Were all steps actually executed?
- If a step was supposed to produce data (SQL), is there actual data in the result (not empty/null)?
- If a PDF was generated, does the file actually exist and is it non-empty?
- If an email draft was produced, are all required fields present (to, subject, body)?

### Check 2 — Data sanity
- Do numbers make sense? (e.g. sales should not be negative; a "total" should roughly match the parts if both are available)
- Are dates/months valid? (e.g. not "month 13")
- Basic reasonableness — this is a lightweight check, not a full audit. Flag obvious anomalies.

### Check 3 — PII / Sensitive data redaction
- Scan the final response text for patterns that look like sensitive data that should not be in a reply:
  - Credit card numbers (4 groups of 4 digits)
  - SSN / national ID patterns (XXX-XX-XXXX)
  - Raw database connection strings or credentials
  - API keys or tokens (long alphanumeric strings that look like secrets)
- If found, REDACT them (replace with [REDACTED]) before the response leaves. Log the redaction.
- This does NOT need to be perfect or catch every edge case — a basic regex-based scan for the most common patterns is sufficient for Phase 5. It can be improved later.

### Check 4 — Business rule compliance (basic)
- Email drafts must have a valid-looking "to" address (contains @).
- SQL queries that ran must have been read-only (double-check; this is a safety net on top of Phase 4's enforcement).
- Reports/PDFs should have a title and at least some content.

---

## How it fits the flow

The existing flow is:
```
Request -> Supervisor -> Planner -> Steps execute (tools) -> Combined answer -> Return to user
```

After Phase 5 it becomes:
```
Request -> Supervisor -> Planner -> Steps execute (tools) -> Combined draft answer
  -> REVIEWER/QA checks the draft
     -> PASS: return to user as-is
     -> FAIL (fixable): retry the failed step (max 1 retry), then re-check
     -> FAIL (not fixable): return to user WITH a clear warning flag (e.g. "[QA WARNING] ...")
  -> Return to user
```

The Reviewer is NOT a separate LLM agent call (to keep it fast and cheap). It is a **deterministic Python validation layer** — a set of functions/checks that inspect the draft answer and tool outputs. No LLM needed for this; rules and regex are sufficient.

Keep it deterministic because:
- It is faster and cheaper (no extra API call).
- It is predictable (same input = same result every time).
- It is easier to test and trust.

---

## Logging

Print clear logs to the backend terminal so the QA behaviour is visible:

- `[QA] checking output...` when the review starts.
- `[QA] PASS` when all checks pass.
- `[QA] FAIL: <reason>` when a check fails (e.g. "[QA] FAIL: email draft missing 'to' field").
- `[QA] RETRY: re-running step <N>` if a fixable failure triggers a retry.
- `[QA] WARNING: <issue>` if a non-fixable issue is flagged to the user.
- `[QA] REDACTED: <type>` if PII was found and redacted (e.g. "[QA] REDACTED: credit card pattern").

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- A deterministic Reviewer/QA validation layer (Python functions, not an LLM agent).
- The four check categories above (completeness, data sanity, PII redaction, business rules).
- Retry logic: if a fixable check fails, retry the relevant step ONCE, then re-check. If it fails again, flag it.
- Terminal logs for all QA activity.
- QA runs on every response, but good responses pass through quickly without adding noticeable delay.

**OUT of scope (DO NOT build — later phases):**
- No failure handling system / dead-letter queue (Phase 6).
- No human-in-the-loop approval flow (Phase 7).
- No real email sending (still draft-only, still Phase 7).
- No smart router (Phase 8).
- No observability dashboard / Langfuse (Phase 9).
- No new tools, no new worker agents, no auth, no multi-tenant.
- Do NOT make the Reviewer an LLM-based agent; keep it deterministic.

If tempted to add human approval, failure queues, or LLM-based review — STOP. Phase 5 is deterministic validation only.

---

## Build order

### Step 1 — Build the QA module
1. Create a separate file (e.g. `backend/qa.py` or `backend/reviewer.py`).
2. Implement each check category as a clear function.
3. Implement the PII scanner (regex-based patterns for credit cards, SSN, credentials, API keys).
4. Implement a main `review(draft_answer, tool_results)` function that runs all checks and returns PASS / FAIL with reasons.

### Step 2 — Wire into the Supervisor flow
1. After the Supervisor has a draft combined answer (but before returning it), call the QA review.
2. If PASS: return as normal.
3. If FAIL (fixable): retry the failed step once, re-review, then return.
4. If FAIL (not fixable / still fails after retry): add a `[QA WARNING]` to the response so the user knows something may be off, and return it.
5. If PII found: redact it before returning, regardless of other checks.

### Step 3 — Test (see checklist below)

---

## "Done" checklist (Phase 5 is complete when ALL are true)

- [ ] **QA runs on every response:** terminal shows `[QA] checking output...` and either `[QA] PASS` or `[QA] FAIL/WARNING` for every request.
- [ ] **Good output passes cleanly:** a normal, correct request (e.g. "what were the sales in June?") gets `[QA] PASS` and the reply is returned as before, with no unnecessary delay or warning.
- [ ] **Incomplete output is caught:** if a step produces empty/missing data (test by asking about a month with no data, or an impossible request), QA flags it with a warning instead of silently returning garbage.
- [ ] **PII redaction works:** if the response somehow contains a credit card pattern or SSN pattern (test by inserting a fake one into the reply scenario, or by testing the QA function directly), it gets redacted to [REDACTED] and the log shows `[QA] REDACTED`.
- [ ] **Email draft validation works:** an email draft missing the "to" field or with an invalid address is caught by QA.
- [ ] **Retry works:** if a fixable failure happens, QA triggers one retry, and if the retry succeeds, the response goes through.
- [ ] Phase 4 tools still work (real SQL, real PDF, draft email). Phase 3 memory still works. Phase 2 Planner still works. Simple requests still work. Frontend unchanged.
- [ ] Errors handled cleanly (QA failure does not crash the system).
- [ ] QA is deterministic (Python functions + regex, NOT an LLM call).

When every box is checked, STOP. Phase 5 is done. Do not start Phase 6 in this same task.

---

## How to verify quickly

1. Run backend and frontend.
2. **Good request:** "what were the sales in June?" → terminal shows `[QA] PASS`, reply comes through normally.
3. **Incomplete/bad request:** ask something that should fail or return empty (e.g. a month that does not exist in the DB) → QA catches it and flags a warning.
4. **PII test:** test the QA function directly (or craft a scenario) with a string containing "4111-1111-1111-1111" or "123-45-6789" → it gets redacted.
5. **Email validation:** ask for an email draft but with a clearly invalid recipient → QA flags it.

If good output passes, bad output is caught, PII is redacted, and nothing crashes, Phase 5 is done.

---

## Notes for later (do not build now)

- Phase 6 adds **failure handling** (retry with backoff -> dead-letter queue -> human alert) for when tools/APIs fail at the infrastructure level (DB down, timeout, etc.).
- Phase 7 adds **human-in-the-loop approval** — risky actions (real email send, large data exports) will pause for human approval before executing. That is when the email tool's "send" capability gets unlocked.
- The QA layer from Phase 5 feeds into both: Phase 6 uses it to decide if a failure is retryable, and Phase 7 uses QA results as input to the approval decision (low QA confidence = require human review).
Keep the QA code modular so more checks can be added later without rewriting.
