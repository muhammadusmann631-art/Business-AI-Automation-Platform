---
name: debug-and-fix-all
description: "Debug and fix all broken features in the AI Agent System (AGI-CORE). The system was built through Phase 0-10 + Level 1 upgrade, but several features are not working correctly in practice: admin panel data add/edit not working, Excel export not producing downloadable files or download card not appearing, dashboard not displaying properly. This skill instructs Claude Code to systematically check, debug, and fix EVERY broken feature, testing each one live before moving on."
---

# Debug & Fix All Broken Features

## Approach — DO NOT guess. CHECK first, then fix.

For EVERY issue below, follow this exact process:
1. **READ** the relevant code files first (frontend + backend).
2. **IDENTIFY** the actual bug (don't assume — find it).
3. **FIX** it.
4. **TEST** it live (start the backend, make a real HTTP request, confirm it works).
5. Only then move to the next issue.

Start the backend server for testing. If there are import errors or startup crashes, fix those FIRST before anything else.

---

## Pre-check — Does the backend even start?

1. Go to the backend directory.
2. Make sure ALL dependencies are installed: `pip install fastapi uvicorn openai python-dotenv fpdf2 openpyxl matplotlib openai-agents --break-system-packages` (or use the venv).
3. Check `requirements.txt` — make sure `openpyxl` and `matplotlib` are listed. If not, add them.
4. Try starting the backend: `python -m uvicorn main:app --port 8000`.
5. If it crashes with ANY import error or startup error — FIX IT before doing anything else. Read the error, find the missing module or syntax issue, fix it.
6. Once the backend starts cleanly, proceed.

---

## Issue 1 — Admin Panel: Data Add/Edit NOT Working

### What should happen:
- User opens `/admin` in the browser.
- Sees 5 tabs: Sales, Customers, Invoices, Products, Expenses.
- Clicks "Add New" → a form appears → fills in fields → clicks Save → new row appears in the table.
- Clicks "Edit" on a row → form with current values → changes something → Save → row updates.
- Clicks "Delete" → confirmation → row removed.

### Debug steps:
1. **Check backend endpoints exist and work:**
   - `GET /api/admin/customers` — does it return a JSON array of customers? Test with curl or /docs.
   - `POST /api/admin/customers` — does it accept a JSON body and create a row? Test with curl.
   - `PUT /api/admin/customers/1` — does it update?
   - `DELETE /api/admin/customers/1` — does it delete?
   - If any endpoint is missing, returns 500, or returns an error — read the code, find the bug, fix it.
   - Common issues: wrong SQL syntax, missing columns in INSERT, database path wrong, table doesn't exist.

2. **Check frontend /admin page:**
   - Read the admin page code (likely `app/admin/page.tsx` or similar).
   - Does it call the correct backend URLs?
   - Does the "Add New" form actually send a POST request?
   - Does it handle the response correctly?
   - Is CORS allowing the request?
   - Common issues: wrong API URL (missing NEXT_PUBLIC_API_URL), form not sending correct JSON fields, button onClick not wired, state not updating after add.

3. **Fix and verify:**
   - After fixing, test the full flow: open /admin → add a customer → see it appear → edit it → see change → delete it → gone.
   - Test with at least 2 different tables (customers + invoices).

---

## Issue 2 — Excel Export NOT Working

### What should happen:
- User asks "customers ki list Excel mein do" or "sales Excel mein export karo".
- Agent calls the export_excel tool.
- A real .xlsx file is created in `backend/exports/`.
- The response includes a `files` array with the download URL.
- The frontend shows a download card (📊 icon + filename + Download button).
- Clicking Download gets the actual .xlsx file.

### Debug steps:
1. **Check the export_excel tool exists and works standalone:**
   - Find the tool function in the code.
   - Does it actually create an .xlsx file using openpyxl?
   - Does `backend/exports/` directory exist? If not, create it.
   - Is `/exports` mounted as StaticFiles in main.py (like `/reports` is for PDFs)?
   - Test: call the tool function directly with sample data — does a valid .xlsx appear in the exports folder?

2. **Check the agent uses the tool:**
   - Does the agent's system prompt mention the export_excel tool?
   - When you ask for Excel export, does the [TOOL CALLED] log appear in the terminal?
   - If the tool is never called — the agent doesn't know about it. Update the agent instructions.

3. **Check the response includes files:**
   - After the tool runs, does the response JSON include `"files": [{"name": "...", "url": "/exports/...", "type": "xlsx"}]`?
   - If not — the code that assembles the response is not picking up the Excel file. Find where PDF files are added to the response and do the same for Excel.

4. **Check frontend renders the download card:**
   - Does the frontend code check for `files` in the response?
   - Does it render a card for xlsx type files?
   - Is the download URL correct? (should be `http://localhost:8000/exports/filename.xlsx`)

5. **Fix and verify:**
   - Ask "customers ki list Excel mein do" → terminal shows [TOOL CALLED] → response has files → frontend shows 📊 card → click downloads real .xlsx → open in Excel → data is there.

---

## Issue 3 — Dashboard NOT Displaying Properly

### What should happen:
- User opens `/dashboard` in the browser.
- Page has the AGI-CORE dark theme (dark background, green/teal accents).
- Shows: stats summary at top (total requests, avg time, total tokens, error rate).
- Shows: list of recent traces (timestamp, message, route, duration, status, tokens).
- Click a trace → expands to show spans (router, planner, tools, QA, response) with timing.
- Shows: feedback section (stats, recent feedback, recurring issues).

### Debug steps:
1. **Check the dashboard page exists:**
   - Is there an `app/dashboard/page.tsx` (or similar)?
   - Does it compile? Run `npx next build` — any errors on the dashboard page?

2. **Check it fetches data:**
   - Does it call `GET /api/traces`? Does that endpoint work? Test with curl.
   - Does it call `GET /api/stats`? Does that endpoint work?
   - Does it call `GET /api/feedback/stats`? Does that endpoint work?
   - If any endpoint returns an error or empty data — fix the endpoint.
   - If the endpoints work but the page is blank — the frontend is not rendering the data. Check the React code for state/rendering bugs.

3. **Check the theme:**
   - Is the dashboard using the same dark theme as the chat page?
   - If colors are wrong (light background, wrong accents), update the CSS/Tailwind classes to match the chat page exactly.
   - Background should be the same dark color as the chat page.
   - Accents should be green/teal/emerald.
   - Text should be light/white.
   - Cards should be dark with subtle green borders.

4. **If no trace data exists yet:**
   - The dashboard may be empty because no traced requests have been made since Phase 9 was built.
   - Start the backend, make 3-4 requests from the chat (mix of simple and complex), THEN check the dashboard — traces should now appear.

5. **Fix and verify:**
   - Open /dashboard → dark theme → stats visible → traces listed → click one → spans expand → feedback section shows.

---

## Issue 4 — General checks (while you're at it)

1. **Chart/graph tool:** Ask "pichle 6 months ki sales ka graph banao" → does a chart image appear INLINE in the chat? If not, debug the make_chart tool and the frontend image rendering.

2. **PDF download card:** Ask "June ki sales report banao" → does the 📄 download card appear? Can you click and download a real PDF?

3. **Email approval:** Ask "send email to test@test.com with sales summary" → do Approve/Reject buttons appear?

4. **LIKE search fix:** Ask "Ahmed ka data dikhao" → does it find partial matches? If not, update the worker prompt to say "use LIKE with % wildcards for name searches".

5. **Header navigation:** Does the header show links to Chat, Dashboard, AND Admin? Do all 3 links work?

---

## "Done" checklist (ALL must pass with live testing)

- [ ] Backend starts without any errors.
- [ ] **Admin Add works:** /admin → Add New customer → save → appears in table → query agent → agent finds it.
- [ ] **Admin Edit works:** /admin → edit a customer → save → change reflected.
- [ ] **Admin Delete works:** /admin → delete a customer → confirm → removed.
- [ ] **Excel export works:** "customers ki list Excel mein do" → 📊 card → click → real .xlsx downloads and opens.
- [ ] **Dashboard displays correctly:** /dashboard → dark AGI-CORE theme → stats + traces + feedback all visible.
- [ ] **Dashboard has data:** after making requests, traces appear in the list and are expandable.
- [ ] **Chart works:** "sales ka graph banao" → chart image appears inline in chat.
- [ ] **PDF works:** "sales report banao" → 📄 card → downloadable PDF.
- [ ] **Email approval works:** "email bhejo" → Approve/Reject buttons appear.
- [ ] **Header has 3 links:** Chat | Dashboard | Admin — all navigable.
- [ ] **All Phase 0-10 features still work.**

Do NOT stop until every checklist item is verified with a LIVE test. If something fails, debug and fix it, then re-test.
