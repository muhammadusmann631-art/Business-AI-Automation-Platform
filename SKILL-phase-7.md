---
name: phase-7-human-in-the-loop-approval
description: "Build Phase 7 of the AI Agent System — add a human-in-the-loop approval flow so risky actions (sending emails, finalizing reports, large data exports) pause for explicit human approval before executing. Low-risk actions continue automatically. This is also the phase where the email tool gains real SEND capability — but ONLY after approval. Use this only after Phase 6 (failure handling: retry, dead-letter, alerts) is complete and verified. This is the safety gate that makes the system enterprise-trustworthy."
---

# Phase 7 — Human-in-the-Loop Approval

## Prerequisite (do not skip)

Phase 0-6 must already be complete and verified:
- Phase 0: frontend <-> FastAPI <-> OpenAI round trip.
- Phase 1: agent + tool loop.
- Phase 2: Supervisor + Planner.
- Phase 3: Memory (short-term + long-term).
- Phase 4: Real business tools (read-only SQL, PDF, draft email).
- Phase 5: QA/Reviewer guardrails.
- Phase 6: Failure handling (retry, dead-letter, alert).

Phase 7 extends the SAME project. Do NOT rebuild anything from scratch.

---

## Goal (read this first)

Right now, once the Supervisor decides to do something, it just does it — no human gets a chance to review or stop it. For low-risk actions (looking up data, making a summary) this is fine. But for HIGH-RISK actions (sending an email to a client, finalizing a report for external use, large data changes), the system must PAUSE and ask a human for approval.

In Phase 7, add an approval gate:

> Before any high-risk action executes, the system pauses, shows the human exactly what it is about to do (the draft email, the report, the action details), and waits for explicit "approve" or "reject". Only after approval does the action execute. Low-risk actions continue automatically without asking.

Also in Phase 7: the email tool gains the ability to ACTUALLY SEND — but ONLY after human approval. Until the human clicks approve, the email stays a draft.

**Phase 7 is complete when:** a high-risk action (like sending an email) pauses for approval, shows the draft, waits for the human's decision, and only executes on "approve". Low-risk actions (like looking up data) run without interruption.

---

## Risk classification — what needs approval and what does not

Build a simple, clear risk classifier. Keep it rule-based (not LLM-based) for predictability.

### HIGH-RISK (always require approval):
- **Sending an email** — the user must see the full draft (to, subject, body) and approve before it actually sends.
- **Generating a FINAL report/PDF for external sharing** — if the report is intended for a client or external party (not just for the user to preview).
- **Any action that was flagged by QA (Phase 5)** with a warning — if QA found issues, do not auto-execute; ask the human.
- **Any action the Planner/Supervisor explicitly marks as "needs approval"** — a catch-all for the agent to flag uncertain actions.

### LOW-RISK (automatic, no approval needed):
- Reading/querying data (SQL SELECT).
- Generating a draft (email draft, report preview for the user).
- Summarising or analysing data.
- Looking up preferences from memory.
- Normal chat/conversation.

The classifier should be a simple Python function that takes the action/tool name and context and returns "requires_approval" or "auto". Keep it in a separate module so the rules can be updated easily.

---

## How it should work (the approval flow)

### For LOW-RISK actions:
Same as before — execute automatically, return result. No change to the user experience.

### For HIGH-RISK actions:
1. The Supervisor/step execution reaches a high-risk step.
2. Instead of executing it, the system PAUSES and returns a special response to the frontend:
   ```json
   {
     "reply": "I've prepared this action and need your approval before proceeding.",
     "pending_approval": {
       "approval_id": "unique-id-here",
       "action": "send_email",
       "details": {
         "to": "client@acme.com",
         "subject": "June Sales Report",
         "body": "Dear Client, ..."
       },
       "risk_reason": "Sending an email to an external recipient"
     }
   }
   ```
3. The **frontend** shows the pending action details and presents two buttons: **"Approve"** and **"Reject"**.
4. The user clicks one:
   - **Approve** → frontend sends `POST /api/approve` with the approval_id → backend executes the action (e.g. actually sends the email) → returns the result.
   - **Reject** → frontend sends `POST /api/reject` with the approval_id → backend discards the pending action → returns a confirmation that it was cancelled.
5. Log the decision: `[APPROVAL] approved: send_email (id: abc123)` or `[APPROVAL] rejected: send_email (id: abc123)`.

---

## What to build

### Part 1 — Risk classifier module
- Create `backend/approval.py` (or similar).
- A function `classify_risk(action_name, context) -> "requires_approval" | "auto"`.
- Rule-based, not LLM-based. Easy to read and update.

### Part 2 — Pending approval store
- A simple in-memory dict (keyed by approval_id) that holds pending actions waiting for human decision.
- Each entry contains: approval_id, action/tool name, action details (the full draft), the function to execute on approval, timestamp, session_id.
- Pending approvals expire after a reasonable timeout (e.g. 10 minutes) — if no decision comes, the action is cancelled and cleaned up. Log the expiry.
- This does NOT need to be a database; an in-memory dict is fine for Phase 7.

### Part 3 — Two new API endpoints
- `POST /api/approve` — accepts `{ "approval_id": "..." }`, executes the pending action, returns the result, removes it from pending.
- `POST /api/reject` — accepts `{ "approval_id": "..." }`, cancels the pending action, returns a confirmation, removes it from pending.
- Both endpoints need the same try/except error handling as /api/chat.

### Part 4 — Email tool upgrade: real SEND (only on approval)
- Upgrade the existing email tool so it CAN actually send (use a simple email-sending approach — SMTP or a lightweight email API library).
- But the send ONLY happens inside the /api/approve handler, NEVER directly from the agent/tool. The tool still produces a draft; the approval handler triggers the actual send.
- Email credentials (SMTP host/port/user/password or API key) go in backend/.env, never hard-coded, never exposed.
- If email credentials are not configured in .env, the system should still work — it just logs "[EMAIL] send skipped — no credentials configured" and returns success with a note. This way the approval flow works even without a real mail server during development.

### Part 5 — Frontend changes (minimal but needed)
- This is the first phase where the frontend MUST change to support approval.
- When the API response contains `pending_approval`, show:
  - The action details (what is about to happen — e.g. the full email draft).
  - An **"Approve"** button (green/positive).
  - A **"Reject"** button (red/negative).
- On Approve click → call `POST /api/approve` with the approval_id → show the result.
- On Reject click → call `POST /api/reject` with the approval_id → show "Action cancelled."
- When there is no `pending_approval` in the response, everything works exactly as before.
- Keep the UI change minimal and consistent with the existing colorful design. The approval card should look clear and distinct — the user must understand they are making a real decision.

---

## Logging

- `[RISK] action: send_email -> requires_approval (reason: external email)` — when classification happens.
- `[RISK] action: query_sales -> auto` — for low-risk (only log at debug level or skip to keep terminal clean).
- `[PENDING] created approval abc123 for send_email — waiting for human decision` — when a pending approval is created.
- `[APPROVAL] approved: send_email (id: abc123) — executing now` — on approve.
- `[APPROVAL] rejected: send_email (id: abc123) — action cancelled` — on reject.
- `[APPROVAL] expired: send_email (id: abc123) — no decision within timeout` — on expiry.
- `[EMAIL] sent to client@acme.com — subject: June Sales Report` — when email actually sends after approval.
- `[EMAIL] send skipped — no credentials configured` — when credentials missing (dev mode).

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- Risk classifier (rule-based, not LLM).
- Pending approval store (in-memory dict).
- /api/approve and /api/reject endpoints.
- Email tool upgraded to actually send (only via approval handler).
- Frontend approval UI (approve/reject buttons when pending_approval is in the response).
- Terminal logs for risk classification, pending, approve/reject, email send.

**OUT of scope (DO NOT build — later phases):**
- No smart router (Phase 8).
- No observability dashboard / Langfuse (Phase 9).
- No feedback loop system (Phase 10).
- No role-based access control (RBAC) for approvals — any user can approve in Phase 7. RBAC can be added later.
- No approval via Slack/email/mobile push — approval happens in the chat UI only.
- No multi-tenant isolation.
- No new tools or agents beyond what exists.

---

## "Done" checklist (Phase 7 is complete when ALL are true)

- [ ] **Risk classifier works:** high-risk actions (email send, flagged reports) are classified as "requires_approval"; low-risk actions (data query, summary) are classified as "auto". Terminal shows `[RISK]` logs.
- [ ] **Low-risk actions are unaffected:** data queries, summaries, lookups all run automatically as before, no approval prompt.
- [ ] **High-risk actions pause for approval:** requesting an email send returns a `pending_approval` response with full draft details instead of executing.
- [ ] **Frontend shows approval UI:** when pending_approval is in the response, approve/reject buttons appear with the action details.
- [ ] **Approve works:** clicking Approve calls /api/approve → the action executes → result is returned. Terminal shows `[APPROVAL] approved` and (if email) `[EMAIL] sent` or `[EMAIL] send skipped — no credentials`.
- [ ] **Reject works:** clicking Reject calls /api/reject → action is cancelled → "Action cancelled" is shown. Terminal shows `[APPROVAL] rejected`.
- [ ] **Email can actually send (on approval):** if SMTP/email credentials are in .env, the email really sends after approval. If credentials are missing, it gracefully skips with a log.
- [ ] **Pending approvals expire:** if no decision comes within the timeout, the pending action is cleaned up and logged.
- [ ] Phase 6 failure handling still works. Phase 5 QA still works. Phase 4 tools still work. Phase 3 memory still works. Phase 2 Planner still works.
- [ ] Errors handled cleanly — invalid approval_id, expired approval, and system errors all return clean messages, no crash.

When every box is checked, STOP. Phase 7 is done. Do not start Phase 8 in this same task.

---

## How to verify quickly

1. Run backend and frontend.
2. **Low-risk test:** "what were the sales in June?" → runs automatically, no approval prompt. ✅
3. **High-risk test:** "send an email to client@test.com with June's sales summary" → response shows pending_approval with full draft → frontend shows Approve/Reject buttons.
4. **Approve test:** click Approve → terminal shows `[APPROVAL] approved` and `[EMAIL] sent` (or `send skipped` if no credentials) → UI shows success.
5. **Reject test:** trigger another email send, but this time click Reject → terminal shows `[APPROVAL] rejected` → UI shows "Action cancelled."
6. **Normal queries still work** — nothing is broken.

If low-risk runs automatically, high-risk pauses, approve executes, reject cancels, and nothing crashes — Phase 7 is done.

---

## Notes for later (do not build now)

- Phase 8 adds a **smart router** to save cost (simple requests skip the full pipeline).
- Phase 9 adds **observability** (Langfuse tracing so every agent call is visible in a dashboard).
- Phase 10 adds the **feedback loop** (user corrections improve future responses).
- Later, RBAC can be layered on top of Phase 7 so different roles (admin, manager, staff) have different approval rights. The current classifier returns "requires_approval" — RBAC would add "requires_approval_from: manager".
- Approval can later be extended to Slack/email/push notifications, so the approver does not need to be watching the chat.
