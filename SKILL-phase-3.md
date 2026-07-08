---
name: phase-3-memory
description: "Build Phase 3 of the AI Agent System — add memory so the system remembers context within a conversation (short-term) and remembers user preferences across sessions (long-term). Use this only after Phase 2 (Supervisor + Planner) is complete and verified. This gives the planning brain a memory, BEFORE real business tools are added in Phase 4. Keep it simple: in-session history plus a lightweight persistent preference store."
---

# Phase 3 — Memory (short-term + long-term)

## Prerequisite (do not skip)

Phase 0, 1, and 2 must already be complete and verified:
- Phase 0: colorful Next.js frontend <-> FastAPI <-> OpenAI round trip.
- Phase 1: one agent + one placeholder tool via the OpenAI Agents SDK.
- Phase 2: Supervisor + Planner producing an ordered plan, executing steps in order, returning one combined reply.

Phase 3 extends that SAME backend. Do NOT rebuild anything from scratch.

---

## IMPORTANT context — still no real business tools yet

The get_sales tool is still a PLACEHOLDER. Real business tools (real SQL against a real database, real PDF/report, real Excel, real email) come in Phase 4, NOT here.

Phase 3 is about giving the brain a MEMORY:
- Phase 2 gave the system the ability to plan.
- Phase 3 gives it the ability to remember.
- Phase 4 will add real business tools.

Do not add real business tools in this phase.

---

## Goal (read this first)

Right now every request starts from zero — the system forgets everything between turns. In Phase 3, add memory so that:

> Within a conversation, the system remembers what was said earlier (short-term). Across sessions, the system remembers the user's stated preferences (long-term).

That behaviour — "remember the conversation so far, and remember preferences for next time" — is the ENTIRE goal of Phase 3.

**Phase 3 is complete when:** (1) a follow-up message that refers back to an earlier turn is understood correctly without repeating the details, and (2) a preference stated once is still applied in a brand-new conversation.

---

## Two kinds of memory to build

### 1. Short-term memory (conversation history, within a session)
- Keep the running conversation (the back-and-forth of the current chat) and pass the relevant history into the Supervisor/agents so follow-up messages have context.
- Example: user says "get June's sales", then says "now summarise that" — the system must know "that" = the June sales result from the previous turn.
- Storage: simplest acceptable approach is an in-memory store keyed by a conversation/session id (a Python dict is fine for Phase 3). A lightweight store is enough; do NOT stand up a full database cluster for this.

### 2. Long-term memory (user preferences, across sessions)
- Persist simple, durable facts/preferences the user states, so they survive a restart and apply in future conversations.
- Example: user says "always keep graphs blue" -> store that -> in a later, separate conversation the system still knows graphs should be blue.
- Storage: keep it lightweight and persistent. A small JSON file on disk (e.g. preferences.json) OR a single simple table is acceptable for Phase 3. Do NOT build a heavy database layer — that comes later when real business needs arrive.

Keep both stores small and clearly separated in the code so they can be swapped for a proper database in a later phase.

---

## How it should work (flow)

1. Each request carries (or is assigned) a conversation/session id so short-term history can be tracked. If the frontend does not send one, the backend can generate/manage one; only make the smallest frontend change needed (ideally none, or just passing an id).
2. On each request, the Supervisor gets: the new message + the recent conversation history (short-term) + any stored preferences (long-term).
3. If the user states a preference (e.g. "always ... "), save it to the long-term store.
4. The plan/answer should take history and preferences into account.
5. Log memory activity to the backend terminal for verification, e.g. "[MEMORY] loaded 2 preferences", "[MEMORY] saved preference: graphs=blue", "[MEMORY] session abc has 3 prior turns".
6. Keep the same {"reply": ...} JSON contract and the existing try/except.

Keep it simple. This is about proving memory works, not building a production memory system.

---

## Scope guard — what is IN and what is OUT

**IN scope:**
- Short-term in-session conversation history passed into the agents.
- A lightweight persistent preference store (JSON file or one simple table).
- Memory logs printed to the backend terminal for verification.
- The smallest possible change to support a session/conversation id.

**OUT of scope (DO NOT build — later phases):**
- No real business tools (real SQL/database queries, real PDF, real Excel, real email). Phase 4.
- No vector database / embeddings / semantic memory (ChromaDB). A later phase can upgrade long-term memory to that; Phase 3 stays simple.
- No Redis/Postgres/Mongo cluster setup. Lightweight storage only.
- No new worker agents, no guardrails, no auth, no human-approval.
- Do not redesign the frontend.

If tempted to add a vector DB, real tools, or a full database — STOP. Phase 3 is lightweight short-term history + a small persistent preference store.

---

## "Done" checklist (Phase 3 is complete when ALL are true)

- [ ] **Short-term memory works:** in one conversation, a follow-up like "now summarise that" correctly refers to the previous turn's result without the user repeating details. Terminal shows the session has prior turns.
- [ ] **Long-term preference is saved:** stating a preference (e.g. "always keep graphs blue") is stored persistently, and the terminal logs the save (e.g. "[MEMORY] saved preference ...").
- [ ] **Long-term preference persists across sessions:** after restarting the backend / starting a fresh conversation, the stored preference is loaded and still applies (terminal logs it being loaded).
- [ ] Phase 2 behaviour still works: multi-step requests still produce a [PLAN], run steps in order, still call the placeholder tool, and return one combined reply.
- [ ] Simple requests ("hi") still work normally.
- [ ] Frontend still works (same JSON contract; at most a minimal session-id change).
- [ ] Errors handled cleanly (no crash).
- [ ] Scope respected: lightweight memory only — no vector DB, no real business tools, no heavy database, no extra agents.

When every box is checked, STOP. Phase 3 is done. Do not start Phase 4 (real business tools) in this same task.

---

## How to verify quickly

1. Run backend and frontend as before.
2. **Short-term test:** send "get June's sales", then in the next message send "now give me a one-line summary of that." The system should summarise the June result without you repeating "June sales". Terminal shows prior-turn context.
3. **Long-term save test:** send "always keep graphs blue." Terminal should log the preference being saved.
4. **Long-term persistence test:** restart the backend, start a fresh chat, and ask something where the preference is relevant (or simply check the preference is reloaded on startup via the "[MEMORY] loaded ..." log). The blue-graph preference should still be known.

If follow-ups are understood and the preference survives a restart, Phase 3 is done.

---

## Notes for later (do not build now)

- Phase 4 will replace the placeholder tool with REAL business tools (real SQL against a real database, real report/PDF, real Excel, real email) — this is where the system starts doing real professional work.
- A later phase can upgrade long-term memory from a simple JSON/table to a proper database and/or a vector store (ChromaDB) for semantic recall. Keep the memory code isolated so this swap is easy.
