---
name: auth-whatsapp-and-duplicate-fix
description: "Add authentication (login/signup with protected routes), WhatsApp integration (Twilio API), and fix the duplicate tool call bug (graphs/PDFs appearing twice). These three changes make the system professional, secure, and multi-channel. Use this after Phase 0-10 + Level 1 + deployment are complete."
---

# Auth + WhatsApp + Duplicate Fix

## IMPORTANT — Build order

1. **Fix duplicate tool calls FIRST** (smallest, most annoying bug).
2. **Auth SECOND** (security — everything must be protected before WhatsApp opens another channel).
3. **WhatsApp THIRD** (new channel — needs auth context to know which user is messaging).

---

## Part 1 — Fix Duplicate Tool Calls (CRITICAL BUG)

### Problem
When the user asks "June ki sales ka graph dikhao" or "PDF report banao", the tool gets called TWICE — two identical graphs or two identical PDFs are generated. This is unprofessional and wastes resources.

### Root cause (check these)
The most common reasons for duplicate tool calls in an agent system:

1. **Agent calling tool twice in one turn** — the LLM decides to call the same tool again. Fix: update the worker/agent prompt.
2. **Step execution loop running a step twice** — the supervisor/step loop has a bug. Fix: add deduplication.
3. **Planner creating duplicate steps** — the plan has two steps that do the same thing. Fix: update planner prompt.

### Fix — apply ALL of these:

**Fix A — Worker/Agent prompt update:**
Add this to the worker agent's system prompt (instructions):
```
IMPORTANT RULES:
- Call each tool ONLY ONCE per request. Never call the same tool twice with the same or similar parameters.
- If you have already called a tool and received its result, use that result. Do not call it again.
- One graph per request. One PDF per request. One Excel per request. One email draft per request.
```

**Fix B — Planner prompt update:**
Add this to the planner agent's prompt:
```
PLANNING RULES:
- Never create duplicate steps. Each tool should appear AT MOST ONCE in the plan.
- "Get data" and "make chart" are separate steps — but never have TWO "make chart" steps.
- Keep plans minimal: 2-4 steps maximum.
```

**Fix C — Code-level deduplication (safety net):**
In the step execution code (wherever tools are called in sequence), add a simple deduplication check:
```python
# Track which tools have been called this request
_tools_called_this_request = set()

def execute_tool(tool_name, params):
    # Create a dedup key from tool name + core params
    dedup_key = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
    if dedup_key in _tools_called_this_request:
        print(f"[DEDUP] skipping duplicate call: {tool_name}")
        return previous_result_for_this_tool  # return cached result
    _tools_called_this_request.add(dedup_key)
    # ... actual tool call ...
```
This is a safety net — even if the LLM tries to call a tool twice, the code catches it.

Reset `_tools_called_this_request` at the START of each new request.

**Fix D — Response file deduplication:**
Before returning the response, deduplicate the `files` array (if present) — remove duplicate filenames/URLs:
```python
if "files" in response:
    seen = set()
    unique_files = []
    for f in response["files"]:
        if f["url"] not in seen:
            seen.add(f["url"])
            unique_files.append(f)
    response["files"] = unique_files
```

### Verify:
- "June ki sales ka graph dikhao" → ONE chart, not two.
- "PDF report banao" → ONE PDF, not two.
- "Excel mein do" → ONE file, not two.
- Terminal shows `[DEDUP] skipping duplicate call` if the LLM tries twice.

---

## Part 2 — Authentication (NextAuth.js)

### What to build

A complete login/signup system so that:
- Unauthenticated users see ONLY the login page — nothing else.
- After login, they see the full AGI-CORE system (chat, dashboard, admin).
- Sessions persist (user stays logged in across browser refreshes).
- Each user has their own session/memory (Phase 3 memory is per-user).

### Tech choice: NextAuth.js (free, built into Next.js)

Use **NextAuth.js** (now called Auth.js) with **Credentials Provider** (email + password). This is the simplest setup that works without any external auth service.

### What to build — Frontend:

**1. Login page (`app/login/page.tsx`):**
- Clean, professional login form: email + password + "Sign In" button.
- "Don't have an account? Sign Up" link.
- AGI-CORE dark theme (same as the rest of the app).
- Error messages for wrong credentials.
- On successful login → redirect to chat (/).

**2. Signup page (`app/signup/page.tsx`):**
- Registration form: name + email + password + confirm password.
- Basic validation (email format, password min 8 chars, passwords match).
- On successful signup → redirect to login with "Account created" message.
- Same AGI-CORE dark theme.

**3. Protected routes:**
- ALL pages (/, /dashboard, /admin) require authentication.
- If not logged in → redirect to /login.
- Use NextAuth middleware or a wrapper component.

**4. User info in header:**
- Show the logged-in user's name/email in the header.
- Add a "Logout" button/link in the header.

**5. Session provider:**
- Wrap the app in NextAuth's SessionProvider.
- Pass the session to API calls (so the backend knows which user is making requests).

### What to build — Backend:

**1. Users table in the database:**
```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',  -- user, admin
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**2. Auth API endpoints:**
- `POST /api/auth/signup` — create a new user. Hash the password (use bcrypt or similar). Never store plain text passwords.
- `POST /api/auth/login` — verify email + password hash, return a session token (JWT).
- `GET /api/auth/me` — return the current user's info from the token.

**3. Protect existing endpoints:**
- ALL existing /api/* endpoints should check for a valid auth token.
- If no valid token → return 401 Unauthorized.
- Exception: /api/auth/signup and /api/auth/login are public.
- The /health endpoint stays public.

**4. Per-user memory:**
- Phase 3 memory (conversation history + preferences) should now be per-user.
- Key memory/history by user_id, not just session_id.
- Different users should NOT see each other's conversations or preferences.

### Important security rules:
- Passwords are ALWAYS hashed (bcrypt). Never stored as plain text.
- JWT secret lives in backend/.env (never hard-coded).
- Add `JWT_SECRET=some-long-random-string` to .env.
- Auth tokens are passed in the Authorization header or as HTTP-only cookies.
- No user data leaks between different users.

### Seed a default admin user:
On database seed, create a default admin:
- Email: `admin@agicore.com`
- Password: `admin123` (for testing only — document that this should be changed)
- Role: `admin`

---

## Part 3 — WhatsApp Integration (Twilio)

### What to build

A WhatsApp channel so users can message the AGI-CORE system from WhatsApp and get the same responses as the web UI.

### How it works:
```
User sends WhatsApp message
  → Twilio receives it
  → Twilio calls YOUR webhook (POST /api/whatsapp)
  → Your backend processes it through the same Supervisor/Planner pipeline
  → Backend sends the reply back via Twilio API
  → User sees the reply in WhatsApp
```

### What to build — Backend:

**1. WhatsApp webhook endpoint (`POST /api/whatsapp`):**
- Receives incoming messages from Twilio.
- Twilio sends: `From` (phone number), `Body` (message text), and possibly `MediaUrl0` (if image/file attached).
- Extract the message, identify the user by phone number.
- Run the message through the SAME pipeline as /api/chat (router → supervisor → planner → tools → QA → response).
- Send the reply back via Twilio's API.
- Handle the response format for WhatsApp (plain text, no HTML — strip any markdown/HTML tags).

**2. Twilio reply function:**
```python
from twilio.rest import Client

def send_whatsapp_reply(to_number: str, message: str):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(
        body=message,
        from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
        to=f"whatsapp:{to_number}"
    )
```

**3. Environment variables (backend/.env):**
```
# Twilio WhatsApp Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=+14155238886
```

**4. WhatsApp-specific handling:**
- **Long responses:** WhatsApp has a 1600 character limit per message. If the response is longer, split it into multiple messages.
- **Files (PDF/Excel/Charts):** WhatsApp can receive media. If the response includes a file, send it as a media message using the public URL (the Render deployment URL + file path). If the file URL is not publicly accessible, send a text message with the download link instead.
- **Approval flow:** If a response needs human approval (email send), send the draft via WhatsApp with options: "Reply APPROVE to send, or REJECT to cancel." Handle the next message as the approval decision.
- **Memory:** Use the phone number as the session identifier for conversation history. WhatsApp users get the same memory features as web users.

**5. Twilio webhook validation (security):**
- Validate that incoming requests actually come from Twilio (not someone spoofing).
- Use Twilio's request validation: check the `X-Twilio-Signature` header against your auth token.
- If validation fails, return 403.

**6. Add `twilio` to requirements.txt:**
```
twilio
```

### Frontend — WhatsApp status page (optional but nice):

Add a small section on the /dashboard showing WhatsApp status:
- Connected / Not configured.
- Recent WhatsApp messages (from the traces — they go through the same pipeline).
- This is optional — the WhatsApp integration works without any frontend change.

### Important notes:
- The Twilio credentials are NOT added by this code — the USER will add them to .env after getting a Twilio account.
- If Twilio credentials are missing from .env, the /api/whatsapp endpoint should return a clear error: "WhatsApp not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER in .env"
- The webhook URL the user gives to Twilio will be: `https://business-ai-automation-platform.onrender.com/api/whatsapp`

---

## Build order (strict)

1. Fix duplicate tool calls (Part 1) — test it.
2. Build auth backend (users table, signup/login/me endpoints, protect routes) — test it.
3. Build auth frontend (login/signup pages, protected routes, session) — test it.
4. Build WhatsApp webhook + Twilio reply — test it.
5. Final integration test (all features work together).

---

## "Done" checklist

### Duplicate fix:
- [ ] "Graph dikhao" → ONE graph, not two.
- [ ] "PDF banao" → ONE PDF, not two.
- [ ] "Excel do" → ONE file, not two.
- [ ] Terminal shows [DEDUP] if LLM tries duplicate call.

### Auth:
- [ ] Login page exists at /login with AGI-CORE dark theme.
- [ ] Signup page exists at /signup.
- [ ] Unauthenticated users are redirected to /login (cannot access chat/dashboard/admin).
- [ ] Login with correct credentials → redirected to chat, works normally.
- [ ] Wrong credentials → error message shown.
- [ ] User name/email shown in header + Logout button works.
- [ ] Passwords are hashed (not plain text) in the database.
- [ ] Different users have separate memory/conversations.
- [ ] Default admin user (admin@agicore.com / admin123) is seeded.
- [ ] Backend endpoints return 401 without valid auth token.
- [ ] JWT_SECRET is in .env, not hard-coded.

### WhatsApp:
- [ ] POST /api/whatsapp endpoint exists and handles Twilio webhook format.
- [ ] If Twilio credentials are missing → clear error message, no crash.
- [ ] If credentials are set → incoming WhatsApp message is processed through the same pipeline as web chat.
- [ ] Reply is sent back via Twilio API.
- [ ] Long responses are split into multiple WhatsApp messages.
- [ ] File responses (PDF/Excel) include download links.
- [ ] Approval flow works via WhatsApp ("Reply APPROVE/REJECT").
- [ ] `twilio` is in requirements.txt.
- [ ] Twilio request validation is implemented.

### Overall:
- [ ] All Phase 0-10 + Level 1 features still work.
- [ ] Frontend AGI-CORE dark theme is consistent across login/signup/chat/dashboard/admin.
- [ ] No regressions.

---

## How to verify

1. **Duplicate fix:** ask for a graph twice in different requests → one graph each time.
2. **Auth:** open the app in incognito → should see login page. Sign up → login → chat works → logout → back to login.
3. **WhatsApp (if Twilio configured):** send a WhatsApp message to the Twilio number → get a response → send "June ki sales" → get real data back.
4. **WhatsApp (without Twilio):** hit POST /api/whatsapp with a test payload → get a clear "not configured" message (no crash).
