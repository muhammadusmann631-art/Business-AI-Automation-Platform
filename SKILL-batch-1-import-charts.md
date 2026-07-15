---
name: batch-1-csv-import-and-dashboard-charts
description: "Add two features: (1) CSV/Excel file import — users upload a file on the admin page or chat, system parses it and adds data to the database automatically. (2) Dashboard live business charts — revenue trend, expense breakdown, top customers, pending invoices — so the dashboard shows real business status at a glance, not just traces."
---

# Batch 1 — CSV/Excel Import + Dashboard Live Charts

## Build order: Import FIRST, then Charts.

Import first because charts need data to display — importing gives us more data to chart.

---

## Feature 1 — CSV/Excel Import

### What it does
User uploads a CSV or Excel file → system reads it, detects columns, maps them to the right database table, and imports the data. No manual typing. Thousands of rows in seconds.

### Where it works (TWO places):

**Place A — Admin Panel (/admin page):**
- Each table tab (Customers, Invoices, Products, Sales, Expenses) gets an **"Import CSV/Excel"** button.
- User clicks it → file picker opens → selects a .csv or .xlsx file.
- System reads the file, shows a PREVIEW (first 5 rows + detected columns) → user confirms → data is imported into that table.
- Show: "X rows imported successfully" or errors if any rows failed.

**Place B — Chat (conversational import):**
- User can say in chat: "import this file into customers" and attach/upload a file.
- Agent reads the file, confirms the table, imports.
- This is secondary — admin panel import is the primary method.

### Backend — what to build:

**1. Import endpoint:**
`POST /api/admin/import/{table}` — accepts a file upload (multipart/form-data).

**2. File parsing logic (backend/importer.py):**
```python
def parse_file(file) -> list[dict]:
    """Read CSV or Excel file, return list of row dicts"""
    if filename.endswith('.csv'):
        # Use csv module or pandas
        # Handle different encodings (utf-8, latin-1)
        # Handle different delimiters (comma, semicolon, tab)
    elif filename.endswith(('.xlsx', '.xls')):
        # Use openpyxl
    
    return rows  # list of dicts, keys = column headers
```

**3. Column mapping:**
- Auto-detect which columns in the file match which database columns.
- Match by name (case-insensitive, fuzzy): "Customer Name" → "name", "E-mail" → "email", "Phone Number" → "phone", "Amount" → "amount", etc.
- If a column can't be matched → skip it (don't crash).
- If a required column is missing → return an error explaining which column is needed.

**4. Import logic:**
- Insert rows one by one (or batch) into the target table.
- Skip duplicate rows (use INSERT OR IGNORE or check for existing).
- Track: how many succeeded, how many failed, why they failed.
- Return: `{ "imported": 45, "skipped": 3, "errors": ["Row 12: missing email field"] }`

**5. Preview endpoint (optional but professional):**
`POST /api/admin/preview-import/{table}` — same file upload, but returns only the first 5 rows + detected column mapping WITHOUT importing. User reviews, then confirms with the actual import endpoint.

### Frontend — Admin panel changes:

**1. Import button on each table tab:**
- Styled button: "📥 Import CSV/Excel" — AGI-CORE dark theme.
- Click → file input opens (accept: .csv, .xlsx, .xls).

**2. Preview modal (after file selected):**
- Show: filename, row count, detected columns → mapped to table columns.
- Show first 5 rows as a preview table.
- "Confirm Import" button (green) and "Cancel" button.

**3. Result display:**
- After import: "✅ 45 rows imported, 3 skipped" with details.
- If errors: show which rows failed and why.

### Important rules:
- File size limit: 5MB max (prevent huge uploads on free tier).
- Validate data types: amounts should be numbers, emails should have @, dates should be valid.
- Never overwrite existing data — only ADD new rows. If user wants to replace, they delete first via admin panel.
- Log: `[IMPORT] customers: 45 rows imported from clients.csv, 3 skipped`.

---

## Feature 2 — Dashboard Live Business Charts

### What it does
The /dashboard page currently shows traces, stats, and feedback. Now add a **Business Overview** section at the TOP with live charts showing the company's actual business data.

### What charts to show (4 charts):

**Chart 1 — Revenue Trend (Line Chart)**
- X-axis: months (last 6-12 months).
- Y-axis: total sales amount per month.
- Shows: revenue going up or down over time.
- Data source: `SELECT month, SUM(amount) FROM sales GROUP BY month ORDER BY month`.

**Chart 2 — Expense Breakdown (Pie/Donut Chart)**
- Segments: expense categories (salary, rent, utilities, marketing, supplies, other).
- Shows: where the money is going.
- Data source: `SELECT category, SUM(amount) FROM expenses GROUP BY category`.

**Chart 3 — Top 5 Customers (Horizontal Bar Chart)**
- Y-axis: customer names.
- X-axis: total revenue from each customer.
- Shows: who brings the most business.
- Data source: `SELECT c.name, SUM(s.amount) FROM sales s JOIN customers c ON s.customer_id = c.id GROUP BY c.id ORDER BY SUM(s.amount) DESC LIMIT 5`.

**Chart 4 — Invoice Status (Donut/Pie Chart)**
- Segments: paid, pending, overdue, cancelled.
- Shows: payment health at a glance.
- Data source: `SELECT status, COUNT(*) FROM invoices GROUP BY status`.

### Backend — new endpoint:

`GET /api/dashboard/business-stats` — returns all data needed for the 4 charts in one call:
```json
{
  "revenue_trend": [
    { "month": "January", "amount": 12000 },
    { "month": "February", "amount": 15000 },
    ...
  ],
  "expense_breakdown": [
    { "category": "salary", "amount": 50000 },
    { "category": "marketing", "amount": 12000 },
    ...
  ],
  "top_customers": [
    { "name": "Ahmed Corp", "revenue": 85000 },
    { "name": "Tech Solutions", "revenue": 62000 },
    ...
  ],
  "invoice_status": [
    { "status": "paid", "count": 15 },
    { "status": "pending", "count": 8 },
    { "status": "overdue", "count": 5 },
    ...
  ],
  "summary": {
    "total_revenue": 450000,
    "total_expenses": 280000,
    "net_profit": 170000,
    "active_customers": 12,
    "pending_invoices": 8,
    "overdue_invoices": 5
  }
}
```

### Frontend — Dashboard page changes:

**1. Business Overview section at the TOP of /dashboard (BEFORE traces):**
- Section title: "📊 Business Overview"
- 4 charts in a 2x2 grid layout.
- Below the charts: summary cards showing key numbers (total revenue, total expenses, net profit, active customers, pending invoices, overdue invoices).

**2. Chart library:**
- Use **Recharts** (already available in React/Next.js, lightweight, good looking).
- Install: `npm install recharts`
- All charts use AGI-CORE dark theme colors:
  - Background: transparent (inherits dark page background).
  - Chart colors: greens/teals (#10b981, #14b8a6, #059669, #0d9488) for positive data.
  - Red/amber for negative/warning data (overdue, high expenses).
  - Text/labels: white/light gray.
  - Grid lines: subtle dark gray.

**3. Auto-refresh:**
- Charts refresh every 60 seconds (or manual refresh button).
- Show a small "Last updated: X seconds ago" text.

**4. Responsive:**
- Desktop: 2x2 grid.
- Mobile: single column (charts stack vertically).

### Important:
- Charts should load FAST — the endpoint returns all data in one call, not separate calls per chart.
- If a table is empty (no data), show "No data yet" in that chart area (don't crash or show blank).
- The existing traces/feedback sections stay — business charts are ABOVE them, not replacing them.

---

## "Done" checklist

### CSV/Excel Import:
- [ ] Admin panel has "📥 Import CSV/Excel" button on each table tab.
- [ ] Clicking it opens a file picker (accepts .csv, .xlsx, .xls).
- [ ] After file selected, a preview shows (first 5 rows + column mapping).
- [ ] Confirm → data imported into the correct table. Success message shows count.
- [ ] Duplicate rows are skipped (not duplicated).
- [ ] Invalid rows show error messages (which row, what's wrong).
- [ ] File size limit enforced (5MB max).
- [ ] Import logged in terminal: `[IMPORT] table: X rows imported`.
- [ ] Different file formats work: CSV (comma/semicolon/tab separated) and Excel (.xlsx).

### Dashboard Business Charts:
- [ ] /dashboard has a "Business Overview" section at the top with 4 charts.
- [ ] Revenue Trend (line chart) shows monthly sales data.
- [ ] Expense Breakdown (pie/donut) shows spending by category.
- [ ] Top 5 Customers (bar chart) shows highest revenue customers.
- [ ] Invoice Status (pie/donut) shows paid/pending/overdue counts.
- [ ] Summary cards below charts show key numbers (revenue, expenses, profit, etc.).
- [ ] All charts use AGI-CORE dark theme colors (green/teal on dark background).
- [ ] Charts handle empty data gracefully ("No data yet").
- [ ] GET /api/dashboard/business-stats returns all chart data in one call.
- [ ] Charts auto-refresh or have a refresh button.
- [ ] Existing traces/feedback sections are still there (below the charts).

### Overall:
- [ ] All Phase 0-10 + Level 1 features still work.
- [ ] No regressions.
- [ ] AGI-CORE dark theme consistent everywhere.

---

## How to verify

1. Go to /admin → Customers tab → click "Import CSV/Excel" → upload a CSV with 10 customers → preview shows → confirm → "10 rows imported" → customers appear in the table.
2. Go to /dashboard → see 4 live charts with actual data from the database.
3. Import more data via CSV → refresh dashboard → charts update with new data.
4. Ask in chat "kitne customers hain?" → count includes the imported ones.
