---
name: phase-2-supervisor-and-planner
description: "Build Phase 2 of the AI Agent System — add a Supervisor agent and a Planner agent on top of the single agent+tool from Phase 1, so a single user request can be understood, broken into small ordered steps, and executed step by step. Use this only after Phase 1 (one agent + one tool via the OpenAI Agents SDK) is complete and verified. This introduces the first multi-agent 'team' and the planning brain, BEFORE memory (Phase 3) or real business tools (Phase 4)."
---

# Phase 2 — Supervisor + Planner (the planning brain)

## Prerequisite (do not skip)

Phase 0 and Phase 1 must already be complete and verified:
- Phase 0: colorful Next.js frontend <-> FastAPI <-> OpenAI round trip works.
- Phase 1: the backend runs ONE agent with ONE tool via the OpenAI Agents SDK, and it has been proven that the agent decides to call the tool and uses its result.

Phase 2 extends that SAME backend. Do NOT rebuild anything from scratch.

---

## IMPORTANT context — the Phase 1 tool is a PLACEHOLDER

The get_sales tool from Phase 1 (and any single demo tool) is a throwaway used only to prove the agent-plus-tool loop. It is NOT a real business tool. Real, professional business tools (a real SQL query tool against a real database, real PDF/report generation, real Excel analysis, real email sending) are built LATER, in Phase 4.

Phase 2 is about the BRAIN, not the hands:
- Phase 2 = the system learns to understand a request and PLAN it into steps.
- Phase 3 = the system learns to remember (memory).
- Phase 4 = real business tools get added.

So in Phase 2, keep using the existing placeholder tool as the only real action. The goal here is planning and coordination, not doing real business work yet.

---

## Goal (read this first)

Right now a single agent handles everything in one shot. In Phase 2, introduce TWO coordinating agents so that a request is handled as a small ordered plan instead of one blind step:

> A user request is received by a Supervisor. The Supervisor uses a Planner to break the request into a short ordered list of steps. Those steps are then executed in order (using the existing agent/tool where relevant), and a final combined answer is returned.

That behaviour — "understand -> plan into steps -> execute steps in order -> combine into a final answer" — is the ENTIRE goal of Phase 2.

**Phase 2 is complete when:** a multi-step request produces a visible PLAN (an ordered list of steps), those steps run in order, and a sensible final answer comes back.

---

## Scope guard — what is IN and what is OUT

**IN scope (build only this):**
- A **Supervisor agent** (the manager/orchestrator): receives the request, gets a plan, drives execution, returns the final answer.
- A **Planner agent**: takes the request and outputs a short, ordered list of steps (e.g. 2-4 steps). Plain text or a simple structured list is fine.
- Wire these on top of the existing Phase 1 agent + placeholder tool.
- Make the generated PLAN visible in the backend terminal logs (print the steps), so the planning behaviour can be verified.
- Optionally (nice to have, not required): also return the plan to the frontend so the user can see the steps. Only do this if it does not require redesigning the frontend.

**OUT of scope (DO NOT build these yet — later phases):**
- No memory / context store / conversation history persistence. That is Phase 3.
- No real business tools (real SQL to a database, real PDF, real Excel, real email). Those are Phase 4. Keep using the Phase 1 placeholder tool only.
- No databases (Postgres, Mongo, Redis, ChromaDB).
- No Research / Coding / Report / QA / Reviewer agents yet. ONLY Supervisor + Planner (plus the one existing worker/tool).
- No guardrails, auth, human-approval, streaming, or cost tracking.
- Do not add more than these two new agents.

If tempted to add memory, a database, or real business tools — STOP. Phase 2 is only the Supervisor and the Planner.

---

## How it should work (flow)

1. Request comes in to /api/chat.
2. The **Supervisor** receives it.
3. The Supervisor asks the **Planner** to produce an ordered list of steps for this request.
4. The plan is printed to the backend terminal (e.g. "[PLAN] 1. get June sales  2. summarise the number").
5. The Supervisor executes the steps in order. For any step that needs the placeholder tool, it uses the existing Phase 1 agent/tool. For simple reasoning/summarising steps, a normal model call is fine.
6. The Supervisor combines the results into ONE final reply and returns it in the same {"reply": ...} JSON shape so the frontend keeps working.
7. Keep the existing try/except so failures return a clean error, not a crash.

Keep the number of steps small (2-4). This is coordination practice, not a complex workflow engine.

---

## "Done" checklist (Phase 2 is complete when ALL are true)

- [ ] There are now a Supervisor agent and a Planner agent, in addition to the existing Phase 1 worker/tool.
- [ ] **Planning works:** a multi-step request (e.g. "get June's sales and give me a one-line summary") causes the Planner to produce an ordered list of steps, and that plan is printed in the backend terminal (e.g. "[PLAN] ...").
- [ ] **Ordered execution works:** the steps run in order and the placeholder tool is still called when a step needs it (the [TOOL CALLED] log still appears for the relevant step).
- [ ] **Final answer is combined:** the user gets ONE sensible final reply that reflects the steps (e.g. the June number plus a short summary), not just raw fragments.
- [ ] **Simple request still works:** a plain question (e.g. "hello") does not need a big plan and still returns a normal reply without breaking.
- [ ] The frontend still works unchanged (same JSON contract).
- [ ] Errors are handled cleanly (no crash on failure).
- [ ] Only Supervisor + Planner were added — no memory, no database, no real business tools, no extra agents.

When every box is checked, STOP. Phase 2 is done. Do not start Phase 3 (Memory) in this same task.

---

## How to verify quickly

1. Run backend and frontend as before.
2. In the UI, send a multi-step request, e.g. **"get June's sales and give me a one-line summary."**
   - The backend terminal should print a **[PLAN]** with ordered steps.
   - The **[TOOL CALLED] get_sales(June)** log should still appear for the data step.
   - The UI should show ONE combined final answer (the number + a short summary).
3. In the UI, send a plain message like **"hi"** — it should still get a normal reply without a heavy plan and without breaking.

If the plan appears, the steps run in order, the tool still fires, and a clean combined answer comes back, Phase 2 is done.

---

## Notes for later (do not build now)

- Phase 3 will add **Memory** (short-term in-session + long-term), so the system remembers context and preferences across turns.
- Phase 4 will replace the placeholder tool with **real business tools** (real SQL against a real database, real report/PDF, real Excel, real email) — this is where the system starts doing actual professional work.
Write the Supervisor and Planner cleanly and separately so that in later phases more worker agents and real tools can be plugged in without rewriting the coordination logic.
