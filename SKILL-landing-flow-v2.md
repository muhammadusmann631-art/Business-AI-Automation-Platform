---
name: landing-flow-and-agent-showcase
description: "Improve the landing page flow so the landing page ALWAYS shows first when the URL is opened (even for logged-in users) until they click 'Let's Go' / 'Enter'. Also expand the landing page to showcase ALL the system's agents and components (Planner, Memory, Router, QA, Trace, Approval, Resilience, etc.) so visitors understand the full system. Establish a clean professional flow: Landing → Login → Chat."
---

# Landing Flow + Agent Showcase

## Context

The landing page exists but has two issues:
1. **Logged-in users skip it** — they get redirected straight to /chat. The user wants the landing page to ALWAYS show first when the URL is opened, for EVERYONE, until they explicitly click "Enter" / "Let's Go".
2. **It doesn't showcase the system's full power** — it should display ALL the agents/components (like the orbit diagram in the chat) so visitors understand this is a serious multi-agent system, not a simple chatbot.

---

## Change 1 — Landing page ALWAYS shows first (the main change)

### New behavior:
- When ANYONE opens the app URL (`/`) — logged in OR logged out — they see the **landing page FIRST**.
- The landing page has a clear "Enter AGI-CORE" / "Let's Go" button (and Login/Sign Up in the nav).
- Only when they click "Enter" / "Let's Go" do they proceed:
  - If already logged in → go to /chat.
  - If not logged in → go to /login (then after login → /chat).
- Do NOT auto-redirect logged-in users away from the landing page. They must SEE it and choose to enter.

### How to implement:
- Remove the auto-redirect useEffect that currently sends logged-in users from `/` to `/chat`.
- The `/` route always renders the landing page component.
- The landing page's primary button behavior:
  - If user is logged in → button says "Enter AGI-CORE →" and navigates to /chat.
  - If user is NOT logged in → button says "Get Started Free" and navigates to /signup, plus a "Login" option.
- Optional nicety: if logged in, show a small "Welcome back, {name}" in the nav with the "Enter AGI-CORE →" button prominent.

### Important:
- This means EVERY visit to the root URL shows the landing page. This is intentional — it's the front door.
- Logged-in users are NOT logged out — they stay logged in, they just see the landing first and click to enter.
- /chat, /dashboard, /admin remain directly accessible via their URLs for logged-in users (only the root `/` shows landing).

---

## Change 2 — Showcase ALL agents/components on the landing page

### Add a new section to the landing page: "Inside AGI-CORE"

This section shows the full multi-agent architecture so visitors see the depth of the system. Use a visual similar to the orbit/core diagram in the chat app (the glowing central "AGI-CORE" with components around it), OR a clean grid of component cards.

### The components to showcase (with one-line descriptions each):

**Orchestration:**
- **Supervisor** — "The manager. Understands your request and coordinates everything."
- **Planner** — "Breaks complex requests into clear, ordered steps."
- **Router** — "Decides the fastest path — simple questions get instant answers, complex ones get the full pipeline."

**Intelligence:**
- **Memory** — "Remembers your conversation and preferences across sessions."
- **Worker** — "Executes each step using the right tools."

**Data & Tools:**
- **Database** — "Securely queries your sales, customers, invoices, and expenses (read-only)."
- **Report** — "Generates professional PDF reports."
- **Excel** — "Exports data to spreadsheets."
- **Charts** — "Creates visual graphs from your data."
- **Email** — "Drafts and sends professional emails."

**Safety & Quality:**
- **QA / Reviewer** — "Checks every output for accuracy, completeness, and sensitive data before it reaches you."
- **Approval** — "Pauses risky actions (like sending emails) for your explicit approval."
- **Resilience** — "Retries on failure, never loses your work, alerts on problems."

**Insight & Learning:**
- **Tracer** — "Records every step for full transparency — see exactly what happened."
- **Feedback** — "Learns from your corrections to improve over time."
- **Alerts** — "Proactively warns you about overdue invoices, low stock, and more."

### How to present it:
- Option A (recommended): reuse the orbit/core visual from the chat — a central glowing "AGI-CORE" with these components arranged around it. If a component is hovered/clicked, show its description. This is very impressive and on-brand.
- Option B: a clean responsive grid of component cards, grouped by category (Orchestration, Intelligence, Data & Tools, Safety & Quality, Insight & Learning). Each card: icon, name, one-line description. Dark theme, subtle green borders.
- Either way: this section clearly communicates "this is a serious, complete AI system with many specialized parts working together."

### Section intro text:
Title: "Inside AGI-CORE — A team of specialized agents"
Subtitle: "Not a simple chatbot. A complete system where each agent has a job — planning, remembering, querying, checking, and learning — all working together so you don't have to."

---

## Change 3 — Professional flow polish

Establish and verify this clean flow:

```
Open URL (/)
  → LANDING PAGE (always, for everyone)
     → "Get Started Free" (logged out) → /signup → account created → /login
     → "Login" (logged out) → /login → success → /chat
     → "Enter AGI-CORE →" (logged in) → /chat
  → CHAT (the main app)
     → header nav: Chat | Dashboard | Admin | Logout
```

### Additional flow rules:
- After **signup** → redirect to /login with a success message ("Account created! Please log in.").
- After **login** → redirect to /chat (the working app), NOT back to landing.
- **Logout** → redirect to the landing page (`/`), logged out.
- The landing page nav should adapt: logged out shows "Login / Sign Up"; logged in shows "Enter AGI-CORE →" and maybe the user's name.

---

## "Done" checklist

- [ ] **Landing always first:** opening `/` shows the landing page for EVERYONE — logged in and logged out. No auto-redirect away from it.
- [ ] **Logged-in enter button:** logged-in users see "Enter AGI-CORE →" on the landing, which takes them to /chat when clicked.
- [ ] **Logged-out buttons:** logged-out users see "Get Started Free" (→ signup) and "Login" (→ login).
- [ ] **Agent showcase section:** the landing page has an "Inside AGI-CORE" section showing all the components (Supervisor, Planner, Router, Memory, Worker, Database, Report, Excel, Charts, Email, QA, Approval, Resilience, Tracer, Feedback, Alerts) with one-line descriptions.
- [ ] **Showcase is visual:** either the orbit/core diagram or a clean categorized card grid, matching AGI-CORE dark theme.
- [ ] **Flow works:** signup → login → chat. Login → chat. Logout → landing. Enter button (logged in) → chat.
- [ ] **Direct routes still work:** logged-in users can still go directly to /chat, /dashboard, /admin via URL.
- [ ] **Not logged out unexpectedly:** showing the landing to logged-in users does NOT log them out.
- [ ] **Responsive:** landing (including the showcase section) looks good on mobile and desktop.
- [ ] **AGI-CORE dark theme** consistent throughout.
- [ ] All existing features still work. No regressions.

---

## How to verify

1. Log in → then open `/` (root) → landing page appears (NOT auto-redirected to chat) → "Enter AGI-CORE →" button visible → click → goes to chat.
2. Open `/` in incognito (logged out) → landing page → "Get Started" → signup → login → chat.
3. On the landing page, scroll to "Inside AGI-CORE" → see all agents/components with descriptions.
4. Logout → lands on the landing page, logged out.
5. Logged-in user types /dashboard directly → dashboard opens (direct routes still work).
6. Check mobile → landing + showcase responsive.
