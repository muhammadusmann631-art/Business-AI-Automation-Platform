---
name: deploy-to-render
description: "Prepare the AI Agent System (AGI-CORE) for deployment on Render.com. Both backend (FastAPI) and frontend (Next.js) will be deployed as separate Web Services, but the frontend proxies API calls to the backend so the end user only needs ONE URL. This skill handles all code changes needed before deploying."
---

# Deploy to Render — Code Preparation

## Goal

Make the codebase ready for Render deployment so that:
- Backend (FastAPI) runs as a Render Web Service.
- Frontend (Next.js) runs as a Render Web Service.
- Frontend proxies all /api/* calls to the backend — user only needs the frontend URL.
- Everything works the same as localhost but now accessible to anyone on the internet.

## Important: SQLite limitation

Render's free tier has an ephemeral filesystem — files (including SQLite .db files) are lost on every redeploy/restart. For NOW this is acceptable because:
- The seed data re-populates on every startup (idempotent seeding).
- This is for demo/MVP purposes.
- Later, switch to Render PostgreSQL for persistent data.

The same applies to generated PDFs, Excel files, and charts — they will be temporary. This is fine for demo.

---

## Changes to make

### 1. Backend — make it Render-ready

**File: backend/main.py — use PORT from environment**

Render sets a `PORT` environment variable. The backend must listen on that port, not hardcoded 8000.

At the bottom of main.py (if there is an `if __name__` block), or in the start command, use:
```python
import os
port = int(os.environ.get("PORT", 8000))
```

**File: backend/requirements.txt — make sure ALL dependencies are listed**

Verify these are ALL present (add any missing):
```
fastapi
uvicorn
openai
python-dotenv
fpdf2
openpyxl
matplotlib
openai-agents
```

**CORS — allow the Render frontend URL**

In main.py where CORS is configured, change it to allow ALL origins for now (we'll restrict later with auth):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Create backend start script**

Create a file `backend/start.sh`:
```bash
#!/bin/bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```
Make it executable (or use the command directly in Render).

### 2. Frontend — proxy API calls to backend

**File: frontend/next.config.js (or next.config.ts) — add rewrites**

Add rewrites so that when the frontend calls `/api/anything`, it gets proxied to the backend Render URL. This is how we achieve "one URL":

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
      {
        source: '/reports/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/reports/:path*`,
      },
      {
        source: '/exports/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/exports/:path*`,
      },
      {
        source: '/charts/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/charts/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

This means:
- User opens `https://agi-core.onrender.com` (frontend).
- When chat sends a message, it calls `/api/chat` → Next.js rewrites it to the backend URL automatically.
- PDF/Excel/Chart downloads also proxy through.
- User never sees the backend URL. One URL experience.

**Frontend API calls — use relative URLs**

Make sure ALL fetch calls in the frontend use RELATIVE URLs (not absolute localhost URLs):
- `fetch('/api/chat', ...)` ✅ (correct — will be rewritten)
- `fetch('http://localhost:8000/api/chat', ...)` ❌ (wrong — won't work on Render)

Search all frontend files for `localhost:8000` or `NEXT_PUBLIC_API_URL` usage in fetch calls and change them to relative paths:
- `/api/chat` instead of `${NEXT_PUBLIC_API_URL}/api/chat`
- `/api/approve` instead of `${NEXT_PUBLIC_API_URL}/api/approve`
- `/api/reject` instead of `${NEXT_PUBLIC_API_URL}/api/reject`
- `/api/feedback` instead of `${NEXT_PUBLIC_API_URL}/api/feedback`
- `/api/traces` etc.
- `/reports/...` for PDF downloads
- `/exports/...` for Excel downloads
- `/charts/...` for chart images

The rewrites in next.config.js handle the proxying — the frontend code just uses relative paths.

### 3. Create render.yaml (optional but helpful)

Create a `render.yaml` in the project ROOT (not inside backend or frontend):

```yaml
services:
  - type: web
    name: agi-core-api
    runtime: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: SMTP_HOST
        sync: false
      - key: SMTP_PORT
        sync: false
      - key: SMTP_USER
        sync: false
      - key: SMTP_PASSWORD
        sync: false
      - key: EMAIL_FROM
        sync: false
      - key: PYTHON_VERSION
        value: "3.11"

  - type: web
    name: agi-core-web
    runtime: node
    rootDir: frontend
    buildCommand: npm install && npm run build
    startCommand: npm start
    envVars:
      - key: NEXT_PUBLIC_API_URL
        sync: false
      - key: NODE_VERSION
        value: "20"
```

### 4. Git — make sure .gitignore is correct

Check that these are in .gitignore (root level AND backend level):
```
.env
*.db
__pycache__/
node_modules/
.next/
backend/reports/
backend/exports/
backend/charts/
venv/
```

### 5. Push all changes to GitHub

After making all changes, commit and push:
```bash
git add -A
git commit -m "Prepare for Render deployment"
git push
```

---

## "Done" checklist (code preparation)

- [ ] Backend uses PORT from environment variable.
- [ ] Backend CORS allows all origins.
- [ ] Backend requirements.txt has ALL dependencies.
- [ ] Frontend next.config.js has rewrites for /api/*, /reports/*, /exports/*, /charts/*.
- [ ] ALL frontend fetch calls use relative URLs (no localhost).
- [ ] render.yaml exists in project root.
- [ ] .gitignore is correct.
- [ ] Changes pushed to GitHub.

After these code changes, follow the MANUAL Render steps (given separately) to create the services.
