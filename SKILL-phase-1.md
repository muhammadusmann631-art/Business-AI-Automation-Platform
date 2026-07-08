---
name: phase-1-first-agent-and-tool
description: "Build Phase 1 of the AI Agent System — replace the plain direct OpenAI call from Phase 0 with a SINGLE real agent (using the OpenAI Agents SDK) that has exactly ONE simple tool it can decide to call. Use this only after Phase 0 (frontend to FastAPI to OpenAI round trip) is complete and verified. This proves the core agent-plus-tool loop works before any supervisor, planner, or multiple agents are added in later phases."
---

# Phase 1 — First Agent + First Tool

## Prerequisite (do not skip)

Phase 0 must already be complete and working: the colorful Next.js frontend talks to FastAPI, FastAPI calls OpenAI, and a reply shows on screen. Phase 1 builds directly on that same project. Do NOT rebuild the frontend or the backend from scratch — extend the existing Phase 0 code.

---

## Goal (read this first)

In Phase 0, the backend made a **plain, direct OpenAI call** — it just chatted, it never "decided" anything.

In Phase 1, replace that plain call with **one real agent** that has **one tool**, and prove that:

> The agent can DECIDE on its own to call the tool, run it, use the tool's result, and return a correct answer.

That single behaviour — "agent chooses to use a tool and uses its result" — is the ENTIRE goal of Phase 1.

**Phase 1 is complete when:** the user asks something that requires the tool, the agent calls the tool by itself, and the answer is based on the tool's real result (not the model guessing from memory).

---

## Scope guard — what is IN and what is OUT

**IN scope (build only this):**
- Introduce the **OpenAI Agents SDK** in the backend.
- Create exactly **ONE** agent.
- Give that agent exactly **ONE** simple, safe tool.
- Wire the existing /api/chat endpoint to route through this agent instead of the old plain OpenAI call.
- Make it visible (in the backend logs/terminal) when the tool actually gets called, so the behaviour can be verified.

**OUT of scope (DO NOT build these yet — later phases):**
- No Supervisor agent, no Planner agent, no multiple agents. Exactly ONE agent.
- No more than one tool. Exactly ONE tool.
- No database (Postgres, Mongo, Redis, ChromaDB), no memory, no context store.
- No PDF/Excel/email/report tools, no web search.
- No guardrails, QA/reviewer, auth, or human-approval steps.
- No streaming needed; a single response is fine.
- Do not change the frontend beyond what is strictly required (ideally the frontend needs no change at all — it still just sends a message and shows the reply).

If tempted to add a second tool, a second agent, or a database — STOP. Keep Phase 1 to one agent and one tool.

---

## The ONE tool to build

Keep the tool trivial on purpose. Its job is to PROVE the loop, not to be useful yet.

Build a small **"lookup" style tool** that returns data the language model could NOT reliably guess on its own, so that a correct answer is real proof the tool ran. Two acceptable options — pick ONE:

- **Option A (recommended) — a tiny hard-coded sample sales lookup.**
  A function like get_sales(month) that returns a number from a small in-code dictionary, e.g. { "January": 12000, "June": 45000, "December": 38000 }. There is NO database — the numbers live in the code. When asked "what were the sales in June?", the only way to get 45000 right is to actually call the tool.

- **Option B — a simple calculator tool.**
  A function like add(a, b) (or basic arithmetic) that the agent must call to compute a result.

Give the tool a clear name, a clear description, and clearly typed inputs/outputs, following the OpenAI Agents SDK's way of defining tools. The description matters — it is how the agent knows when to use it.

---

## Build order (do these in sequence, test after each)

### Step 1 — Add the Agents SDK and define the tool
1. In the backend/, install and set up the OpenAI Agents SDK.
2. Define the single tool (Option A or B above) as a proper agent tool with name, description, and typed parameters.
3. Add a log/print line INSIDE the tool function (e.g. "[TOOL CALLED] get_sales(June)") so that when it runs, it is visible in the backend terminal. This is important for verification.

### Step 2 — Create the single agent
1. Create one agent using the Agents SDK.
2. Give it a short, clear instruction/system prompt, e.g. "You are a helpful assistant. When the user asks about sales figures, use the get_sales tool to fetch the real number. Do not guess."
3. Register the one tool with this agent.

### Step 3 — Route /api/chat through the agent
1. Change the existing POST /api/chat endpoint so that, instead of the old plain OpenAI call, it runs the user's message through the agent.
2. Return the agent's final reply in the same JSON shape as before ({ "reply": "..." }) so the frontend keeps working unchanged.
3. Keep the try/except error handling so failures return a clean error, not a crash.

### Step 4 — Verify (see checklist below).

---

## "Done" checklist (Phase 1 is complete when ALL are true)

- [ ] The backend now uses the OpenAI Agents SDK with exactly ONE agent and ONE tool.
- [ ] The existing frontend still works unchanged and shows replies.
- [ ] **Tool-triggering question works:** asking something that needs the tool (e.g. "what were the sales in June?" or "what is 5 + 7?") makes the agent call the tool, and the answer matches the tool's real result (e.g. 45000, or 12).
- [ ] The backend terminal shows the [TOOL CALLED] ... log at the moment the tool runs — proving the agent actually used the tool, not its own memory.
- [ ] **Non-tool question still works:** a normal question (e.g. "hello, how are you?") gets a normal reply WITHOUT calling the tool. (The agent should only use the tool when relevant.)
- [ ] Errors are handled cleanly (backend down or tool error → friendly message, no crash).
- [ ] Still only ONE agent and ONE tool — nothing extra was added.

When every box is checked, STOP. Phase 1 is done. Do not start Phase 2 (Supervisor + Planner) in this same task.

---

## How to verify quickly

1. Run backend and frontend (same as Phase 0).
2. In the UI, ask a **tool question** (e.g. "what were the sales in June?"). Watch the backend terminal — you should see the [TOOL CALLED] log, and the UI answer should contain the correct number from the tool.
3. In the UI, ask a **normal question** (e.g. "hi, how are you?"). The terminal should NOT show the tool log, and you should get a normal chat reply.

If both behave correctly, the agent-plus-tool loop is proven and Phase 1 is done.

---

## Notes for later (do not build now)

Phase 2 will add a small **Supervisor** agent and a **Planner** agent on top of this, so one request can be broken into steps and handed to worker agents. Everything in Phase 1 should be written cleanly (tool clearly separated from agent logic) so that adding more agents/tools later is easy — but that is a future task, not now.
