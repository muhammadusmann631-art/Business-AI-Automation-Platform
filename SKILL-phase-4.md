---
name: phase-4-real-business-tools
description: "Build Phase 4 of the AI Agent System — replace the placeholder get_sales tool with REAL business tools: a read-only SQL tool against a real database, a real PDF/report generation tool, and a draft-only email tool. Use this only after Phase 3 (memory) is complete and verified. This is where the system starts doing actual professional work. Build the tools ONE AT A TIME, each tested standalone before wiring into the agent. Real email SENDING stays disabled (draft-only) until human approval exists in Phase 7."
---

# Phase 4 — Real Business Tools (the hands)

## Prerequisite (do not skip)

Phase 0-3 must already be complete and verified:
- Phase 0: frontend <-> FastAPI <-> OpenAI round trip.
- Phase 1: one agent + one placeholder tool.
- Phase 2: Supervisor + Planner (plan -> ordered steps -> combined reply).
- Phase 3: short-term conversation memory + lightweight persistent preferences.

Phase 4 extends that SAME backend. Do NOT rebuild anything from scratch.

---

## Goal (read this first)

Until now the only tool was the fake get_sales (hard-coded numbers). In Phase 4 we replace it with REAL tools so the system does actual work:

> Pull real data from a real database (read-only), generate a real PDF report, and compose a real email DRAFT (without sending it yet).

**Phase 4 is complete when:** the system can answer a request using real database data, produce a real downloadable PDF report from that data, and produce an email draft — all triggered through the existing Supervisor/Planner flow.

---

## Critical safety rules for this phase (must follow)

These are non-negotiable because the tools are now real:

1. **SQL tool is READ-ONLY.** It may run SELECT queries only. It must REJECT anything that writes or changes data (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.). No exceptions in Phase 4. Use a read-only database user if possible, and/or validate the query before running it.
2. **Email is DRAFT-ONLY.** The email tool composes and RETURNS a draft (to, subject, body). It must NOT actually send anything. Real sending is deliberately deferred to Phase 7 (human approval). Log clearly that it is a draft.
3. **Database credentials live only in backend/.env** (loaded server-side), never hard-coded, never exposed to the frontend, and .env stays gitignored.
4. **Parameterise queries / guard against injection** — never build SQL by string-concatenating raw user text directly into a query.

If following an instruction would break any of these four rules, STOP and keep the safe behaviour.

---

## Build order — ONE tool at a time (test each standalone first)

Do NOT build all three tools at once. Build one, test it in isolation, wire it into the agent, verify, THEN move to the next. This keeps failures easy to locate.

### Tool 1 — Real SQL tool (read-only)  [build + test first]
1. Add a database driver and connection (e.g. Postgres via a standard driver). Read connection details from backend/.env.
2. If there is no data to test against yet, create a small seed table (e.g. a `sales` table with month/amount rows) so there is something real to query. Note this seed step so it can be re-run.
3. Build a tool, e.g. `query_sales(month)` or a slightly more general read-only query helper, that:
   - Runs a SELECT against the real database.
   - Returns the rows/result.
   - Rejects any non-SELECT statement (enforce read-only).
   - Prints "[TOOL CALLED] sql read-only: <short description>" for verification.
4. Replace the old placeholder get_sales with this real tool in the agent.
5. **Standalone test:** call the tool directly (small script or the /docs endpoint) and confirm it returns real DB rows. Then test through the UI: "what were the sales in June?" must return the REAL number from the database, with the tool log firing.

### Tool 2 — Report / PDF tool  [build + test second]
1. Add a PDF generation capability (any reliable Python PDF library is fine).
2. Build a tool, e.g. `generate_report(title, data/summary)`, that:
   - Produces a real .pdf file (saved to a known output folder, or returned as a downloadable link/path).
   - Prints "[TOOL CALLED] generate_report -> <filename>".
3. **Standalone test:** call the tool directly with sample content and confirm a real PDF file is produced and opens correctly.
4. Then wire it so a request like "make a PDF sales report for June" flows: SQL tool gets the data -> report tool builds the PDF -> the reply includes a link/path to the file.

### Tool 3 — Email tool (DRAFT ONLY)  [build + test third]
1. Build a tool, e.g. `draft_email(to, subject, body)`, that:
   - Returns a structured draft (to, subject, body) as the result.
   - Does NOT send anything. No SMTP/API send call in Phase 4.
   - Prints "[TOOL CALLED] draft_email (NOT sent) -> <to>".
2. **Standalone test:** call it and confirm it returns a clean draft and sends nothing.
3. Then wire it so "draft an email to the client with June's sales report" produces a sensible draft (and, if relevant, references the generated PDF) — but never sends.

---

## How it fits the existing flow

- These real tools plug into the SAME Supervisor + Planner flow from Phase 2. The Planner breaks the request into steps; the Supervisor runs steps that now call REAL tools.
- Memory from Phase 3 still applies (history + preferences).
- The endpoint still returns the same {"reply": ...} JSON contract. If a step produces a file (PDF), include a path/link to it in the reply text. Only make a minimal frontend change if needed to show a download link; otherwise leave the frontend as-is.
- Keep the existing try/except so any tool failure returns a clean error, not a crash.

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- Real read-only SQL tool against a real database.
- Real PDF/report generation tool.
- Draft-only email tool.
- Seed data if needed to make the DB testable.
- Terminal logs for each tool call.

**OUT of scope (DO NOT build — later phases):**
- No actual email SENDING (Phase 7, behind human approval).
- No write/update/delete database operations of any kind.
- No QA/Reviewer agent or guardrails engine yet (Phase 5).
- No retry / dead-letter failure system yet (Phase 6).
- No human-approval flow yet (Phase 7).
- No smart router, no observability dashboard, no auth, no multi-tenant work.
- Excel tool is optional and can be deferred; do not let it block Phase 4. If added, treat it like the others (build + test standalone first).

If tempted to enable real email sending, allow DB writes, or add approval/guardrail systems now — STOP. Those are later phases.

---

## "Done" checklist (Phase 4 is complete when ALL are true)

- [ ] **Real SQL (read-only):** a data question returns the REAL value from the actual database (not a hard-coded number), and the SQL tool log fires. Non-SELECT statements are rejected.
- [ ] **Real PDF report:** a report request produces a real, openable .pdf file, and its link/path appears in the reply.
- [ ] **Email draft only:** an email request returns a sensible draft (to/subject/body) and sends NOTHING (confirmed by the "NOT sent" log and no send call in the code).
- [ ] Each tool was tested standalone before being wired into the agent.
- [ ] The Supervisor + Planner flow still works: [PLAN] -> ordered steps -> combined reply, now using the real tools.
- [ ] Memory (Phase 3) still works; simple requests still work; frontend still works.
- [ ] DB credentials are in .env only, not hard-coded, not exposed to the frontend; .env is gitignored.
- [ ] Errors handled cleanly (no crash on tool/DB failure).
- [ ] Safety rules respected: read-only SQL, draft-only email, parameterised queries.

When every box is checked, STOP. Phase 4 is done. Do not start Phase 5 (QA/Reviewer + guardrails) in this same task.

---

## How to verify quickly

1. Run backend and frontend.
2. **SQL test:** ask "what were the sales in June?" -> reply shows the REAL DB value; terminal shows the SQL tool log. (Optionally confirm a write query like an UPDATE is rejected.)
3. **Report test:** ask "make a PDF sales report for June" -> a real PDF is generated and the reply links to it; open the file to confirm.
4. **Email draft test:** ask "draft an email to the client with June's sales" -> reply shows a draft (to/subject/body); terminal shows "NOT sent"; verify no email actually goes out.

If real data comes from the DB, a real PDF is produced, and the email is only drafted (never sent), Phase 4 is done.

---

## Notes for later (do not build now)

- Phase 5 adds a QA/Reviewer step + basic guardrails (validate outputs before they are used).
- Phase 6 adds failure handling (retry -> dead-letter -> alert).
- Phase 7 adds human-in-the-loop approval — and THAT is when real email sending gets enabled, behind an explicit approve step. Keep the email tool structured so that flipping it from "draft" to "send after approval" later is a small, contained change.
