---
name: level-1-make-system-useful
description: "Upgrade the AI Agent System (AGI-CORE) from a single-table demo to a real multi-table business system. Add proper business database tables (customers, invoices, products, expenses), new tools (Excel export, data comparison, charts/graphs), improve the system prompt for professional multilingual responses, and add a simple admin panel for data management. Use this after Phase 0-10 + polish fixes are complete."
---

# Level 1 — Make the System Actually Useful

## Context

Phase 0-10 are complete and all fixes are applied. The system works end-to-end: routing, planning, memory, real SQL, PDF reports, email (with approval), QA, retry/dead-letter, tracing, and feedback. BUT it only has one `sales` table with 12 rows of sample data. That is a demo, not a business tool.

This upgrade turns it into something a real business can use. Do NOT rebuild anything — EXTEND the existing system.

---

## Part 1 — Expand the Database (real business tables)

### Add these tables to the existing database (company.db or whichever DB is in use):

**Table: customers**
```sql
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    company TEXT,
    phone TEXT,
    city TEXT,
    status TEXT DEFAULT 'active',  -- active, inactive, lead
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table: invoices**
```sql
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id),
    amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, paid, overdue, cancelled
    due_date DATE,
    paid_date DATE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table: products**
```sql
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',  -- active, discontinued
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Table: expenses**
```sql
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,  -- salary, rent, utilities, marketing, supplies, other
    amount REAL NOT NULL,
    description TEXT,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Seed data (realistic sample data)

Insert realistic-looking sample data so the system is immediately testable:

- **customers**: 15-20 customers with Pakistani/international names, companies, cities (Karachi, Lahore, Dubai, London), mix of active/inactive/lead.
- **invoices**: 25-30 invoices linked to customers, mix of pending/paid/overdue, amounts ranging from $500 to $50,000, dates spread across last 6 months.
- **products**: 10-15 products with categories (Software License, Consulting, Hardware, Service, Training), different prices and stock levels.
- **expenses**: 20-25 expense entries across categories (salary, rent, utilities, marketing, supplies), spread across last 6 months.
- **sales** table (existing): keep it but add a `customer_id` column linking to customers, so sales can be queried per customer.

Make the seed data idempotent (safe to run multiple times — use INSERT OR IGNORE or check before inserting).

### Update the SQL tool

The existing read-only SQL tool must now be aware of ALL tables (not just sales). Update the agent's instructions/system prompt so it knows about customers, invoices, products, expenses, and their columns. The agent should be able to answer questions like:
- "Kitne customers active hain?"
- "Kaun se invoices overdue hain?"
- "Marketing pe is month kitna kharcha hua?"
- "Top 5 customers by revenue?"
- "Kaunsa product sabse zyada bikta hai?"

The read-only safety (SELECT only) stays enforced. No changes to the security model.

---

## Part 2 — New Tools (Excel export, comparison, charts)

Build these as deterministic tools (like Phase 4 — NOT LLM agents). Each tool gets a [TOOL CALLED] log.

### Tool 1 — Excel Export Tool
- Takes a query result (rows of data) and exports it as a downloadable .xlsx file.
- Uses `openpyxl` library (pip install openpyxl).
- Saves to `backend/exports/` folder (create if not exists, mount as StaticFiles like reports/).
- Returns the download URL.
- Example: "June ki sales Excel mein de do" → runs SQL → exports to .xlsx → returns download link.
- Frontend: show a download card (like PDF card) with Excel icon (📊) + filename + Download button.

### Tool 2 — Data Comparison Tool
- Compares two datasets and highlights differences.
- Example: "June vs July ki sales compare karo" → fetches both → shows side-by-side comparison with increase/decrease percentages.
- Output: a structured text comparison (table format in the reply). Does NOT need to be a separate file — inline reply is fine.

### Tool 3 — Simple Chart/Graph Tool
- Generates a simple bar/line chart image from data.
- Uses `matplotlib` library (pip install matplotlib).
- Saves chart as .png to `backend/charts/` folder (mount as StaticFiles).
- Returns the image URL.
- Example: "Pichle 6 months ki sales ka graph banao" → fetches data → generates bar chart → returns image link.
- Frontend: show the chart image inline in the chat (render the image directly, not just a download link).
- Remember user's chart preferences from memory (e.g. "graphs blue rakhna").

### Register all new tools with the existing agent/worker
- Update the worker agent's instructions so it knows about these new tools and when to use them.
- The Planner should now be able to create plans that use these tools: "1. Get data → 2. Make chart → 3. Export Excel → 4. Email to client".

---

## Part 3 — Professional System Prompt

Update the Supervisor/worker agent's system prompt to be professional and business-aware. Replace any generic instructions with:

```
You are AGI-CORE, a professional AI business assistant. You help businesses with data analysis, reporting, and communication.

Capabilities:
- Query business data (sales, customers, invoices, products, expenses) from the database.
- Generate PDF reports with data and analysis.
- Export data to Excel (.xlsx) files.
- Create charts and graphs from data.
- Draft and send emails (with human approval).
- Compare data across time periods.

Behavior rules:
- You understand English, Urdu, and Roman Urdu (Hinglish). Respond in the same language the user uses.
- Be professional but friendly. Give concise, actionable answers.
- When presenting numbers, use proper formatting (commas, currency symbols where appropriate).
- When asked about data, ALWAYS use the database tools — never guess or make up numbers.
- If a request involves multiple steps, break it down clearly.
- If you are unsure about something, say so honestly rather than guessing.

Available database tables:
- sales (month, amount, customer_id) — monthly sales figures
- customers (name, email, company, phone, city, status) — customer directory
- invoices (invoice_number, customer_id, amount, status, due_date) — billing
- products (name, category, price, stock, status) — product catalog
- expenses (category, amount, description, date) — company expenses
```

This prompt goes in the Supervisor AND worker agents. The Planner can keep its existing planning-focused prompt but should also know about all available tools and tables.

---

## Part 4 — Simple Admin Panel (data management)

Add a `/admin` page in the Next.js frontend for basic data management:

### What it should show:
- A tab/section for each table: Sales, Customers, Invoices, Products, Expenses.
- Each section shows a data table (list of rows) with basic columns.
- An "Add New" button to add a row (simple form with the required fields).
- An "Edit" button on each row to modify it.
- A "Delete" button on each row (with confirmation "Are you sure?").
- Keep it simple — this is an internal admin tool, not a public-facing UI.

### Backend endpoints needed:
- `GET /api/admin/{table}` — list all rows in a table.
- `POST /api/admin/{table}` — add a new row.
- `PUT /api/admin/{table}/{id}` — update a row.
- `DELETE /api/admin/{table}/{id}` — delete a row.

### Important:
- These admin endpoints are WRITE endpoints — they bypass the read-only restriction of the agent's SQL tool. This is intentional: the AGENT can only read, but the ADMIN (human) can write.
- The admin panel uses the same AGI-CORE dark theme as the rest of the app.
- Add a link to the admin panel in the header (next to "Dashboard →"), e.g. "Admin →".
- No auth on admin in this phase (auth comes later) — but add a comment noting that auth should protect this in production.

---

## Frontend updates summary

1. **Excel download card** — same style as PDF card but with 📊 icon.
2. **Chart image inline** — render chart .png directly in chat message.
3. **Admin page** at `/admin` — dark theme, table management, CRUD.
4. **Header links** — Chat | Dashboard | Admin — all accessible.

---

## Build order

1. Database tables + seed data FIRST (everything depends on this).
2. Update SQL tool + agent instructions (so agent knows about new tables).
3. Excel export tool + frontend download card.
4. Chart/graph tool + frontend inline image.
5. Comparison tool.
6. System prompt update.
7. Admin panel (backend endpoints + frontend page).

Test after each step.

---

## "Done" checklist

- [ ] **5 tables exist** in the database: sales, customers, invoices, products, expenses — all with realistic seed data.
- [ ] **Agent answers multi-table questions:** "kitne customers active hain?", "overdue invoices dikhao", "marketing expenses kitne hain?" — all return correct data from the database.
- [ ] **Excel export works:** "June ki sales Excel mein do" → download card appears → clicking downloads a real .xlsx file that opens in Excel.
- [ ] **Chart/graph works:** "6 months ki sales ka graph banao" → a real chart image appears inline in the chat. User's color preferences (from memory) are applied.
- [ ] **Comparison works:** "June vs July compare karo" → a clear comparison with percentages appears in the reply.
- [ ] **System prompt is professional:** agent responds in the user's language (English/Urdu/Roman Urdu), uses proper number formatting, never guesses data.
- [ ] **Admin panel exists** at /admin with dark AGI-CORE theme, shows all 5 tables, supports Add/Edit/Delete.
- [ ] **Header has all 3 links:** Chat | Dashboard | Admin.
- [ ] **All Phase 0-10 features still work:** routing, planning, memory, QA, retry, approval, tracing, feedback — nothing broken.
- [ ] **New tools have [TOOL CALLED] logs** and appear in traces (Phase 9).
- [ ] **PDF reports can now include data from any table** (not just sales).
- [ ] **Email drafts can reference any data** (customer info, invoice details, etc.).

---

## How to verify

1. Run backend + frontend.
2. "Kitne customers hain?" → real count from database.
3. "Overdue invoices ki list do" → real invoice list.
4. "Sales ka graph banao pichle 6 months ka" → chart image inline.
5. "June ki sales Excel mein export karo" → download card → real .xlsx.
6. "June vs July sales compare karo" → comparison with percentages.
7. Open /admin → see all tables → add a new customer → ask agent "naye customers dikhao" → new customer appears.
8. Full chain: "Top 5 customers ki sales nikal, chart banao, PDF report banao, aur boss@company.com ko bhejo" → plan bane → sab tools chalein → approval aaye → done.

If all of the above work, Level 1 is complete.
