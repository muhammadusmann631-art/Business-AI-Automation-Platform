---
name: polish-and-fixes
description: "Fix and polish the AI Agent System after Phase 0-10 completion. This addresses real issues found during testing: PDF download links not showing in chat, email approval (Approve/Reject) buttons not appearing, dashboard colors not matching the main AGI-CORE dark theme, and email SMTP credential setup. This is NOT a new phase — it is a fix/polish pass on the existing system."
---

# Polish & Fixes — Make Everything Work End-to-End

## Context

Phase 0-10 are complete. The system works but has these real issues found during testing:

1. **PDF link not clickable in chat** — when a PDF report is generated, the reply mentions it but there is no clickable download link or button in the frontend. The user cannot easily get the PDF.
2. **Email approval not appearing** — when the user asks to send an email, the Approve/Reject buttons do NOT appear. The system either just drafts without offering to send, or the pending_approval is not being returned/rendered properly.
3. **Dashboard colors mismatch** — the main chat UI has the dark sci-fi AGI-CORE green theme, but the /dashboard page has different colors (likely the old purple/light theme). Dashboard must match the AGI-CORE dark theme exactly.
4. **Email credentials not configured** — SMTP is not set up, so even if approval worked, emails cannot actually send.

Fix ALL of these. The system should feel like ONE polished product, not separate pieces glued together.

---

## Fix 1 — PDF Download Link in Chat (CRITICAL)

### Problem
When the user asks "June ki sales report PDF mein banao", the backend generates a real PDF in backend/reports/ and the reply text mentions it, but the frontend chat just shows plain text — no clickable link, no download button.

### What to do
1. **Backend**: make sure the reply includes the PDF URL in a structured way. The response JSON should include a `files` array (or similar) alongside `reply`:
   ```json
   {
     "reply": "Here is your June sales report.",
     "trace_id": "...",
     "files": [
       {
         "name": "june-sales-report.pdf",
         "url": "/reports/june-sales-report-xxxxx.pdf",
         "type": "pdf"
       }
     ]
   }
   ```
   If there are no files, `files` can be an empty array or omitted.

2. **Frontend**: when the response contains `files`, render a download card below the reply message:
   - Show a PDF icon (📄 or a styled icon).
   - Show the filename.
   - A "Download" button that opens/downloads the file.
   - Style it as a card consistent with the AGI-CORE dark theme (dark background, green accent border, clean typography).
   - The download link should point to `http://localhost:8000/reports/filename.pdf` (or use the NEXT_PUBLIC_API_URL env variable).

3. **Test**: ask "June ki sales report banao" → reply shows a styled PDF download card → clicking it downloads the actual PDF.

---

## Fix 2 — Email Approval Flow (CRITICAL)

### Problem
When the user asks "Client@test.com ko email bhejo", the Approve/Reject buttons do NOT appear. The system might be:
- Only drafting (not triggering the approval flow).
- Returning pending_approval but the frontend is not rendering it.
- The risk classifier is not classifying email-send as high-risk.

### What to do — debug and fix the ENTIRE chain:

1. **Risk classifier check** (`backend/approval.py` or wherever classify_risk lives):
   - Make sure ANY request that involves sending/emailing is classified as "requires_approval".
   - Keywords to catch: "send email", "email bhejo", "mail karo", "email to", "send to", "bhej do".
   - Log: `[RISK] action: send_email -> requires_approval`.

2. **Supervisor/main.py flow check**:
   - When a step involves the email tool AND the intent is to SEND (not just draft), the flow must return `pending_approval` in the response instead of executing.
   - Make sure the `pending_approval` object is actually included in the JSON response with all fields: `approval_id`, `action`, `details` (to, subject, body), `risk_reason`.

3. **Frontend check** (`app/page.tsx`):
   - When the response JSON contains `pending_approval`, render the approval card:
     - Show the email draft details (To, Subject, Body) in a styled card.
     - Green "✓ Approve" button and Red "✕ Reject" button.
     - On Approve click → POST /api/approve with approval_id → show result.
     - On Reject click → POST /api/reject with approval_id → show "Cancelled".
   - Make sure this check is actually running — add a console.log to debug if needed.
   - Style the approval card consistent with AGI-CORE dark theme.

4. **Test the full chain**:
   - Ask "send an email to client@test.com with June sales summary".
   - Terminal must show: `[RISK] requires_approval`.
   - Response must contain `pending_approval`.
   - Frontend must show Approve/Reject buttons with email draft.
   - Click Approve → terminal shows `[APPROVAL] approved` → `[EMAIL] sent` or `[EMAIL] send skipped — no credentials`.

---

## Fix 3 — Dashboard Theme (IMPORTANT)

### Problem
The main chat page has the dark AGI-CORE theme (dark background, green/teal accents, sci-fi feel), but the /dashboard page has different colors — it does not look like it belongs to the same product.

### What to do
1. Make the /dashboard page use the EXACT same theme as the main chat page:
   - Same dark background color.
   - Same green/teal accent colors.
   - Same font family and sizing.
   - Same card/container styling (dark cards with subtle green borders).
2. Specifically update:
   - Page background → dark (same as chat page).
   - Trace list items → dark cards with green accent.
   - Stats numbers → green/teal colored.
   - Status badges: success = green, error = red, warning = amber.
   - Expanded trace spans → dark sub-cards.
   - Feedback section → same dark theme.
   - All text → light/white on dark background.
3. The dashboard should feel like navigating within the SAME product, not jumping to a different app.
4. Make sure the "Dashboard →" link in the header and any "← Back to Chat" link are styled consistently.

---

## Fix 4 — Email SMTP Credentials Setup

### What to add in backend/.env
Add these lines to backend/.env (with placeholder comments so the user knows what to fill):

```
# Email SMTP Configuration
# Option 1: Gmail (need App Password — NOT your regular Gmail password)
#   Go to: Google Account → Security → 2-Step Verification → App Passwords
#   Generate one for "Mail" → use that 16-char password below
# Option 2: SendGrid (free 100 emails/day)
#   Sign up at sendgrid.com → Settings → API Keys → create key
#   Use smtp.sendgrid.net, port 587, user "apikey", password = your API key
# Option 3: Resend (free 100 emails/day)
#   Sign up at resend.com → get API key

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here
EMAIL_FROM=your-email@gmail.com
```

### What to do in code
1. Make sure the email sending code in the /api/approve handler reads these from .env.
2. If SMTP credentials are NOT set (empty or missing), the system should:
   - Still allow the approval flow to work (Approve/Reject buttons appear).
   - On Approve: log `[EMAIL] send skipped — no SMTP credentials configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in backend/.env` instead of crashing.
   - Return a clear message to the user: "Email approved but not sent — SMTP not configured."
3. If credentials ARE set:
   - Actually send the email via SMTP.
   - Log: `[EMAIL] sent to client@test.com — subject: June Sales Report`.
4. Never hard-code credentials. Never expose them to the frontend. Keep .env in .gitignore.

---

## Build order

1. Fix 2 (Email Approval) FIRST — this is the most broken feature.
2. Fix 1 (PDF Link) SECOND — important for usability.
3. Fix 3 (Dashboard Theme) THIRD — visual consistency.
4. Fix 4 (SMTP Setup) — add the .env template and make sure the code reads it properly.

Test each fix individually before moving to the next.

---

## "Done" checklist

- [ ] **PDF download works:** asking for a PDF report → reply shows a styled download card with PDF icon + filename + Download button → clicking downloads the actual PDF file.
- [ ] **Email approval works:** asking to send an email → Approve/Reject card appears with full draft details (to, subject, body) → Approve executes (sends or skips with log) → Reject cancels.
- [ ] **Dashboard matches theme:** /dashboard has the same dark AGI-CORE theme as the chat page — same background, same green accents, same fonts, same card styles. Looks like one product.
- [ ] **SMTP .env template exists:** backend/.env has SMTP placeholder lines with clear comments explaining Gmail App Password / SendGrid / Resend options.
- [ ] **No-credentials graceful:** if SMTP is not configured, approval still works but email send is skipped with a clear log and message (no crash).
- [ ] **All Phase 0-10 features still work:** nothing is broken by these fixes.
- [ ] **Frontend is consistent:** PDF cards, approval cards, feedback buttons, dashboard — all use the same AGI-CORE dark theme.

---

## How to verify

1. Run backend + frontend.
2. Ask "June ki sales report PDF mein banao" → styled PDF download card appears → click → real PDF downloads. ✅
3. Ask "send email to test@test.com with June sales" → Approve/Reject card appears with draft → click Approve → terminal shows approval + email skip (no creds). ✅
4. Open /dashboard → dark theme, green accents, matches chat page exactly. ✅
5. Check backend/.env → SMTP lines are there with comments. ✅
