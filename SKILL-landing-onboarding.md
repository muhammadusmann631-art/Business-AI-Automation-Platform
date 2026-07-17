---
name: landing-page-and-onboarding
description: "Add a professional landing page (shown before login) and a first-time user onboarding experience to the AI Agent System (AGI-CORE). The landing page markets the product with a hero section, feature cards, and a call-to-action. Onboarding welcomes new users with sample questions and a quick guide. Both use the exact AGI-CORE dark sci-fi theme. This is the final polish that makes the product look professional to clients."
---

# Landing Page + Onboarding

## Context

The system is complete (Phase 0-10 + Level 1 + auth + WhatsApp + all batches). But when someone opens the URL, they immediately see a login page — no explanation of what the product does. And new users who sign up land in an empty chat with no guidance.

This skill adds two things:
1. A **landing page** at `/` that markets the product (shown to logged-OUT users).
2. **Onboarding** for first-time users (shown after signup).

Both must match the existing AGI-CORE dark theme EXACTLY.

---

## Design system reference (match existing app EXACTLY)

Before building, look at the existing chat/dashboard pages and extract the exact colors/fonts used. The landing page and onboarding MUST use the same:
- Dark background (the same near-black/dark color as the app, e.g. #050807 or whatever the app uses).
- Green/teal/emerald accent colors (#10b981, #14b8a6, #059669 or the app's exact accents).
- Same font family.
- Same card style (dark cards with subtle green borders/glow).
- Same button style (green accent buttons).
- The AGI-CORE logo/branding (the ✦ sparkle icon + "AGI · CORE" text seen in the app).

The landing page should feel like the SAME product as the app — a natural front door, not a different website.

---

## Part 1 — Landing Page

### Route and access logic
- The landing page lives at `/` (root).
- **Logged-OUT users** who visit `/` → see the landing page.
- **Logged-IN users** who visit `/` → redirect straight to the chat (the actual app).
- The chat app moves to `/chat` (or stays at `/` for logged-in users — whichever is cleaner with the existing routing). Make sure existing links (Dashboard, Admin) still work.

### Landing page sections (top to bottom):

**1. Header/Nav bar:**
- Left: AGI-CORE logo (✦ sparkle icon + "AGI · CORE" text, green).
- Right: "Login" button and "Sign Up" button (green accent).
- Sticky/fixed at top, transparent-to-dark on scroll.

**2. Hero section (the main attention-grabber):**
- Large heading: "AGI-CORE — Your AI Business Assistant"
- Subheading: "Ask in plain language. Get reports, charts, emails, and insights — in seconds. The work that takes hours, done in minutes."
- Two buttons: "Get Started Free" (primary green) → goes to /signup, and "Login" (secondary outline) → goes to /login.
- Background: subtle animated gradient or the same glowing-core visual style as the app (if there's an animated core/orbit graphic in the app, reuse that aesthetic here — it's very on-brand).
- Optional: a subtle animated background (floating particles, gradient glow) — keep it tasteful and performant.

**3. Feature cards section (what it does):**
Title: "Everything your business needs, in one assistant"
A grid of 6 feature cards (2 rows x 3, responsive to 1 column on mobile). Each card: an icon, a title, a short description. Use these:

- **💬 Ask Anything** — "Query your sales, customers, invoices, and expenses in plain English or Urdu. No SQL, no spreadsheets."
- **📊 Instant Reports & Charts** — "Generate PDF reports, Excel exports, and visual charts with a single request."
- **📧 Smart Email** — "Draft and send professional emails. Send bulk reminders to all overdue clients at once — with one approval."
- **📱 WhatsApp Ready** — "Manage your business right from WhatsApp. Ask questions, get reports, approve actions — on the go."
- **📈 Profit & Loss + Alerts** — "See your P&L instantly. Get automatic alerts for overdue invoices, low stock, and expense spikes."
- **🎙️ Voice Input** — "Too busy to type? Just speak. Your voice becomes action."

Each card: dark background, subtle green border, hover effect (slight lift + glow). AGI-CORE theme.

**4. "How it works" section (3 steps):**
Title: "How it works"
Three simple steps with icons/numbers:
1. **Ask** — "Type or speak your request: 'Show me June's overdue invoices.'"
2. **AGI-CORE works** — "The system plans, queries your data, and prepares the result — checking everything before it reaches you."
3. **You approve** — "Review and approve important actions. The AI does the work; you stay in control."

**5. Social proof / stats section (optional but professional):**
A row of impressive stats (use realistic placeholder numbers that can be updated):
- "5 min" — "Average time saved per report (vs 3 hours manually)"
- "10+ tools" — "Data, reports, charts, email, and more"
- "24/7" — "Available on web and WhatsApp"
Keep it honest — don't fake customer counts. Focus on capabilities.

**6. Final call-to-action section:**
- Big heading: "Ready to automate your business work?"
- Subtext: "Get started in minutes. No credit card required."
- Big "Get Started Free" button → /signup.

**7. Footer:**
- AGI-CORE logo + tagline.
- Simple links: Login, Sign Up, (and placeholders for Privacy, Terms if you want).
- "Built with AGI-CORE" or your name/brand.
- Copyright line.

### Landing page rules:
- Fully responsive — looks great on mobile (single column) and desktop.
- Fast loading — don't add heavy libraries. Use CSS animations, not heavy JS.
- All "Get Started" / "Sign Up" buttons → /signup. All "Login" buttons → /login.
- Smooth scroll, subtle animations on scroll (fade-in sections) — tasteful, not distracting.
- Consistent AGI-CORE dark theme throughout.

---

## Part 2 — First-Time User Onboarding

### When it shows
- After a user signs up and logs in for the FIRST time → show onboarding.
- Track "has completed onboarding" per user (a flag in the database `users.onboarded` or in localStorage).
- Returning users do NOT see onboarding again.

### Onboarding experience (keep it light — 2 parts):

**Part A — Welcome modal (shown once on first login):**
A centered modal/overlay with AGI-CORE theme:
- Heading: "Welcome to AGI-CORE! 👋"
- Text: "I'm your AI business assistant. I can query your data, make reports and charts, send emails, and more. Let me show you what I can do."
- A short list of "Try asking me:" with 3-4 example prompts.
- A "Let's Go" button that closes the modal.
- A "Skip" link.

**Part B — Sample question chips (in the empty chat):**
When the chat is empty (no messages yet), show clickable suggestion chips above or below the input:
- "Kitne customers active hain?"
- "June ka P&L dikhao"
- "Sales ka graph banao"
- "Overdue invoices dikhao"
- "Customers ki list Excel mein do"

Clicking a chip → fills it into the input OR sends it directly as a message. This helps users understand what to ask without staring at a blank screen.

These chips disappear once the user has sent their first message (or can stay as a small "suggestions" helper).

### Onboarding rules:
- Non-intrusive — user can skip anytime.
- Shows only once per user (track completion).
- Matches AGI-CORE dark theme.
- The sample chips are genuinely useful — even returning users might like a "suggestions" button.

---

## Part 3 — Empty States (small polish)

While building, improve empty states across the app:
- **Empty chat:** instead of blank, show "Ask me anything about your business" + the sample chips.
- **Empty dashboard (no data):** "No data yet. Import a CSV in the Admin panel to see your business come alive." + a link to /admin.
- **Empty admin table:** "No records yet. Add one manually or import a CSV/Excel file."
- **No alerts:** "✅ All clear — no issues need your attention."

All empty states: friendly, on-theme, with a helpful next action.

---

## "Done" checklist

### Landing page:
- [ ] Visiting `/` while logged OUT shows the landing page (not the login form directly).
- [ ] Visiting `/` while logged IN redirects to the chat app.
- [ ] Hero section with heading, subheading, and "Get Started" + "Login" buttons.
- [ ] 6 feature cards with icons, titles, descriptions — AGI-CORE themed.
- [ ] "How it works" 3-step section.
- [ ] Final call-to-action section.
- [ ] Footer with logo and links.
- [ ] All "Get Started"/"Sign Up" buttons → /signup. All "Login" → /login.
- [ ] Fully responsive (mobile single-column, desktop multi-column).
- [ ] Matches AGI-CORE dark theme exactly (same colors, fonts, logo).
- [ ] Fast loading, tasteful animations.

### Onboarding:
- [ ] First-time users see a welcome modal after signup.
- [ ] Welcome modal has example prompts and a "Let's Go" button.
- [ ] Returning users do NOT see the welcome modal again.
- [ ] Empty chat shows clickable sample question chips.
- [ ] Clicking a chip sends/fills that question.
- [ ] Onboarding completion is tracked per user.

### Empty states:
- [ ] Empty chat, dashboard, admin tables, and alerts all have friendly on-theme messages with helpful next actions.

### Overall:
- [ ] All existing features still work (auth, chat, dashboard, admin, WhatsApp, bulk, voice, etc.).
- [ ] Existing routes (Dashboard, Admin) still accessible for logged-in users.
- [ ] No regressions.
- [ ] AGI-CORE dark theme consistent across landing, onboarding, and app.

---

## How to verify

1. Open the app URL in incognito (logged out) → landing page appears with hero, features, CTA.
2. Click "Get Started" → goes to signup. Click "Login" → goes to login.
3. Sign up as a new user → log in → welcome modal appears with example prompts.
4. Close modal → empty chat shows sample question chips → click one → it sends.
5. Log out → visit `/` → landing page again.
6. Log in as existing user → `/` redirects straight to chat (no landing, no onboarding modal).
7. Check mobile view → landing page and app both responsive.
