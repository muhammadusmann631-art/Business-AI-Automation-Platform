---
name: phase-0-plumbing
description: "Build the Phase 0 foundation (the 'spine') of the AI Agent System — a single end-to-end message round trip between a colorful Next.js frontend, a FastAPI backend, and the OpenAI API. Use this whenever setting up the very first working connection of the project, BEFORE any agents, planners, tools, databases, or memory are added. This is the base layer everything else will sit on."
---

# Phase 0 — Plumbing (The Spine)

## Goal (read this first)

Build the smallest possible **end-to-end working line**:

> User types a message in the frontend → it goes to the FastAPI backend → the backend calls the OpenAI API → the reply comes back → it shows on the screen.

That is the ENTIRE goal of Phase 0. Nothing more.

If a user can type "hello" in the UI and see a real OpenAI reply appear below, **Phase 0 is complete.**

---

## Scope guard — what is IN and what is OUT

This is the most important section. Do NOT go beyond scope.

**IN scope (build only this):**
- One Next.js frontend page with a simple, colorful chat UI (input box + send button + message list).
- One FastAPI backend with a single POST endpoint that calls OpenAI and returns the reply.
- Environment/secret handling for the OpenAI API key.
- CORS so the frontend can talk to the backend.

**OUT of scope (DO NOT build these yet — they come in later phases):**
- No Supervisor / Planner / Research / SQL / any agents.
- No OpenAI Agents SDK yet — Phase 0 uses a plain, direct OpenAI API call.
- No databases (Postgres, Mongo, Redis, ChromaDB).
- No memory, no tools, no PDF/email/report generation.
- No authentication, rate limiting, or guardrails.
- No streaming (a plain single response is fine for Phase 0).

If you feel tempted to add any "OUT of scope" item, STOP. Keep Phase 0 tiny.

---

## Tech stack

- **Frontend:** Next.js (App Router) + React + TypeScript. Styling with Tailwind CSS.
- **Backend:** Python + FastAPI + Uvicorn.
- **AI:** OpenAI API (use the official `openai` Python SDK). Use a small, cheap model for Phase 0 (e.g. `gpt-4o-mini`) since this is only a connectivity test.

---

## Recommended project structure

```
project-root/
├── backend/
│   ├── main.py            # FastAPI app + the single /api/chat endpoint
│   ├── requirements.txt   # fastapi, uvicorn, openai, python-dotenv
│   └── .env               # OPENAI_API_KEY=...   (never commit this)
│
└── frontend/
    └── (standard Next.js app)
        └── app/
            └── page.tsx   # the colorful chat UI
```

Keep backend and frontend in separate folders. They run as two separate processes.

---

## Build order (do these in sequence, test after each)

### Step 1 — Backend first

1. Create the `backend/` folder and a Python virtual environment.
2. Install: `fastapi`, `uvicorn`, `openai`, `python-dotenv`.
3. Create `.env` with `OPENAI_API_KEY=...`. Load it with `python-dotenv`. **Never hard-code the key.**
4. In `main.py`, create a FastAPI app with:
   - A single `POST /api/chat` endpoint.
   - It accepts JSON like `{ "message": "hello" }`.
   - It calls the OpenAI API (chat completion) with that message using `gpt-4o-mini`.
   - It returns JSON like `{ "reply": "..." }`.
   - Wrap the OpenAI call in a try/except so that if it fails, the endpoint returns a clean error message (status 500 with a readable reason) instead of crashing.
5. Enable **CORS** for `http://localhost:3000` so the frontend can call it.
6. Add a trivial `GET /health` endpoint that returns `{ "status": "ok" }` for quick testing.

**Test Step 1 before moving on:** run the backend (`uvicorn`), then hit `/health` in the browser, and test `/api/chat` with a tool like `curl` or the FastAPI `/docs` page. Confirm a real OpenAI reply comes back. Do not touch the frontend until this works.

### Step 2 — Frontend

1. Create a Next.js app (App Router, TypeScript) in `frontend/`. Set up Tailwind CSS.
2. In `app/page.tsx`, build a single-page chat UI:
   - A scrollable list of messages (user messages and AI replies visually distinct).
   - A text input at the bottom + a "Send" button.
   - On send: call the backend `POST /api/chat`, show a loading state while waiting, then append the reply to the message list.
   - Handle errors gracefully (if the backend fails, show a friendly inline error, don't break the page).
3. Put the backend URL in an environment variable (e.g. `NEXT_PUBLIC_API_URL=http://localhost:8000`) rather than hard-coding it.

### Step 3 — Connect and verify

Run both processes (backend on port 8000, frontend on port 3000). Type "hello" → confirm a real OpenAI reply appears on screen.

---

## Frontend design direction (make it colorful and modern)

The user specifically wants a **colorful, polished, modern** UI — not a plain default. Aim for something that feels intentional and alive, not a generic template. Follow any available frontend-design skill/guidance for taste and consistency. Concretely:

- **Colorful but tasteful:** use a cohesive palette (a primary accent color plus a soft gradient background works well). Avoid clashing rainbow colors — pick a mood and stay consistent.
- **Chat bubbles:** user and AI messages should look clearly different (e.g. accent-colored bubble aligned right for the user, a lighter/neutral bubble aligned left for the AI). Rounded corners, comfortable padding, good spacing.
- **Typography:** a clean modern font, readable sizes, clear hierarchy.
- **Polish:** subtle shadows, smooth transitions/animations on new messages, a nice loading indicator (typing dots or a spinner) while waiting for the reply.
- **Responsive:** looks good on both desktop and mobile.
- **Empty state:** a friendly welcome message before the first chat.
- Keep it a **single, clean page** — don't over-engineer with routing or many components in Phase 0.

Keep the code readable and well-organized so later phases can build on it.

---

## Environment & secrets rules

- The OpenAI API key lives ONLY in `backend/.env` and is loaded server-side. It must NEVER be exposed to the frontend or committed to git.
- Add a `.gitignore` that excludes `.env`, `node_modules/`, `__pycache__/`, and the Python virtual environment.

---

## "Done" checklist (Phase 0 is complete when ALL are true)

- [ ] Backend runs and `/health` returns ok.
- [ ] `POST /api/chat` returns a real OpenAI reply for a test message.
- [ ] The OpenAI API key is loaded from `.env`, not hard-coded, and is not exposed to the frontend.
- [ ] Frontend runs and shows a colorful, modern chat UI.
- [ ] Typing "hello" in the UI shows a real OpenAI reply on screen.
- [ ] A loading state shows while waiting, and errors are handled without crashing.
- [ ] `.env` and other secrets/large folders are gitignored.

When every box is checked, STOP. Phase 0 is done. Do not start Phase 1 (the first agent + tool) in this same task.

---

## Notes for later (do not build now)

Phase 1 will introduce the first single agent using the OpenAI Agents SDK, plus one simple tool. Everything in Phase 0 should be written cleanly so that swapping the plain OpenAI call for an agent later is easy — but that is a future task, not now.
