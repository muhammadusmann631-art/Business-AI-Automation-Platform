---
name: batch-2-pnl-calculator-and-smart-alerts
description: "Add two features: (1) Profit & Loss Calculator — user asks 'is month ka P&L dikhao' and gets a complete breakdown: total revenue, total expenses (by category), net profit/loss, comparison with previous month. (2) Smart Alerts — system automatically checks for problems (overdue invoices, low stock, expenses over budget, inactive customers) and shows alerts on dashboard + notifies in chat when user logs in."
---

# Batch 2 — P&L Calculator + Smart Alerts

## Build order: P&L FIRST, then Smart Alerts.

P&L first because it establishes the financial analysis pattern. Smart Alerts uses similar queries.

---

## Feature 1 — Profit & Loss Calculator

### What it does

User asks "P&L dikhao" or "profit loss btao" or "is month ka financial summary" → system calculates:
- Total Revenue (from sales table)
- Total Expenses (from expenses table, broken down by category)
- Net Profit or Loss (Revenue - Expenses)
- Comparison with previous month (% change)
- Simple verdict: "Profit hua" or "Loss hua"

This is the #1 thing every business owner wants to see daily.

### Backend — P&L tool

**Create a new tool: `calculate_pnl`**

This is a DETERMINISTIC tool (no LLM needed) — pure SQL + math:

```python
def calculate_pnl(period: str = "current_month") -> dict:
    """
    Calculate Profit & Loss for a given period.
    period can be: "current_month", "last_month", "January", "Q1", "this_year", etc.
    """
    # 1. Get total revenue for the period
    revenue = query("SELECT SUM(amount) FROM sales WHERE month = ?", [period])
    
    # 2. Get expenses broken down by category
    expenses = query("""
        SELECT category, SUM(amount) as total 
        FROM expenses 
        WHERE strftime('%m', date) = ? 
        GROUP BY category
    """, [month_number])
    
    total_expenses = sum(e['total'] for e in expenses)
    
    # 3. Calculate net
    net = revenue - total_expenses
    status = "PROFIT" if net > 0 else "LOSS"
    
    # 4. Get previous period for comparison
    prev_revenue = query(...)
    prev_net = ...
    change_pct = ((net - prev_net) / abs(prev_net)) * 100 if prev_net else 0
    
    return {
        "period": period,
        "revenue": revenue,
        "expenses": {
            "total": total_expenses,
            "breakdown": expenses  # [{category, total}, ...]
        },
        "net": net,
        "status": status,  # "PROFIT" or "LOSS"
        "comparison": {
            "previous_period": prev_period,
            "previous_net": prev_net,
            "change_percent": change_pct,
            "trend": "UP" if change_pct > 0 else "DOWN"
        }
    }
```

Log: `[TOOL CALLED] calculate_pnl(June) → PROFIT $17,000`

**Register with agent:**
Update the worker agent instructions:
```
- When user asks about profit, loss, P&L, financial summary, or "kitna kamaya" → use the calculate_pnl tool.
- Present the result clearly with revenue, expenses breakdown, net profit/loss, and comparison.
```

### How agent should present P&L:

When the user asks "June ka P&L dikhao", the response should be clean and structured:

```
📊 June 2025 — Profit & Loss

Revenue:        $45,000
Expenses:       $28,000
  ├ Salary:     $15,000
  ├ Marketing:   $5,000
  ├ Rent:        $4,000
  ├ Utilities:   $2,500
  └ Supplies:    $1,500
                ────────
Net Profit:     $17,000 ✅

vs May: ↑ 12% improvement ($15,200 → $17,000)
```

The agent should format this nicely in the reply. NOT make a PDF or chart unless the user specifically asks.

### P&L on Dashboard too:

Add a small P&L summary card to the dashboard Business Overview section:
- Current month's Revenue, Expenses, Net Profit/Loss.
- Green if profit, red if loss.
- Small arrow showing trend vs last month.

### Flexible periods:
The tool should understand different period formats:
- "June" or "June 2025" → specific month.
- "is month" / "current month" → current month.
- "pichle month" / "last month" → previous month.
- "Q1" / "pehli quarter" → January-March aggregate.
- "is saal" / "this year" / "2025" → full year aggregate.
- "June vs July" → comparison (show both side by side).

---

## Feature 2 — Smart Alerts

### What it does

System AUTOMATICALLY checks for business problems and alerts the user. The user does NOT need to ask — system proactively tells them.

### Where alerts show (THREE places):

**Place 1 — Dashboard alert banner:**
At the top of /dashboard (above Business Overview), show an alert section:
- 🔴 Critical alerts (red) — overdue invoices, serious issues.
- 🟡 Warning alerts (amber) — low stock, high expenses, approaching due dates.
- 🟢 Info alerts (green) — positive milestones, improvements.
- Each alert is a single line with an icon, message, and timestamp.
- Dismissable (user can click X to hide an alert).

**Place 2 — Chat welcome message:**
When user opens the chat (or starts a new session), if there are active alerts, show them as the first message:
```
⚠️ 3 alerts need your attention:
🔴 5 invoices are overdue (total: $23,000)
🟡 Product "Widget Pro" stock is low (2 remaining)  
🟡 Marketing expenses are 40% over last month
```

**Place 3 — WhatsApp (if configured):**
Optionally: send a daily summary of alerts via WhatsApp at a set time. This is optional for now — chat + dashboard alerts are the priority.

### What to check (alert rules):

Build these as separate, clear check functions in `backend/alerts.py`:

**Alert 1 — Overdue Invoices (CRITICAL 🔴):**
```python
def check_overdue_invoices() -> list[Alert]:
    """Find invoices where status='pending' AND due_date < today"""
    overdue = query("SELECT * FROM invoices WHERE status='pending' AND due_date < date('now')")
    if overdue:
        total = sum(i['amount'] for i in overdue)
        return [Alert(
            level="critical",
            message=f"{len(overdue)} invoices overdue (total: ${total:,.0f})",
            details=[f"INV-{i['invoice_number']}: ${i['amount']:,.0f} — {i['customer_name']}" for i in overdue]
        )]
    return []
```

**Alert 2 — Low Stock Products (WARNING 🟡):**
```python
def check_low_stock(threshold=5) -> list[Alert]:
    """Products where stock < threshold"""
    low = query("SELECT * FROM products WHERE stock < ? AND status='active'", [threshold])
    if low:
        return [Alert(
            level="warning",
            message=f"{len(low)} products have low stock",
            details=[f"{p['name']}: {p['stock']} remaining" for p in low]
        )]
    return []
```

**Alert 3 — Expense Spike (WARNING 🟡):**
```python
def check_expense_spike(threshold_pct=30) -> list[Alert]:
    """Any expense category where this month > last month by threshold%"""
    # Compare current month vs previous month per category
    # If any category jumped by >30%, alert
```

**Alert 4 — Approaching Due Dates (WARNING 🟡):**
```python
def check_approaching_dues(days=3) -> list[Alert]:
    """Invoices due within the next N days"""
    upcoming = query("SELECT * FROM invoices WHERE status='pending' AND due_date BETWEEN date('now') AND date('now', '+3 days')")
```

**Alert 5 — Inactive Customers (INFO 🟢):**
```python
def check_inactive_customers(months=3) -> list[Alert]:
    """Customers with no sales in the last N months"""
```

**Alert 6 — Positive Milestone (INFO 🟢):**
```python
def check_milestones() -> list[Alert]:
    """Revenue hit a new monthly high, or all invoices paid, etc."""
```

### Backend — what to build:

**1. Alert module (`backend/alerts.py`):**
- Alert dataclass/model: level (critical/warning/info), message, details, timestamp, dismissed.
- `run_all_checks() -> list[Alert]` — runs all 6 checks, returns combined alerts sorted by level (critical first).
- Each check is independent — if one fails, others still run.

**2. Alert endpoint:**
- `GET /api/alerts` — returns current alerts.
- `POST /api/alerts/dismiss/{alert_id}` — dismiss an alert (hides it until it triggers again).

**3. Alert check timing:**
- Run checks on every `/api/alerts` call (simple approach).
- Cache results for 5 minutes (don't run 6 SQL queries on every page load).
- Alerts auto-refresh on dashboard every 60 seconds.

**4. Chat integration:**
- When `/api/chat` is called and it's the first message of a session, prepend active alerts to the Supervisor's context: "Note: there are N active alerts: [list]. Mention them to the user if relevant."
- The agent can naturally mention: "By the way, you have 5 overdue invoices worth $23,000. Want me to show details or send reminders?"

### Frontend — Dashboard alert section:

**Alert banner at the top of /dashboard:**
```
┌──────────────────────────────────────────────────────┐
│ ⚠️ ALERTS (3 active)                                │
│                                                      │
│ 🔴 5 invoices overdue ($23,000 total)          [✕]  │
│ 🟡 Widget Pro: only 2 in stock                [✕]  │  
│ 🟡 Marketing expenses up 40% vs last month    [✕]  │
│                                                      │
│ 🟢 June revenue hit a new monthly high! 🎉    [✕]  │
└──────────────────────────────────────────────────────┘
```

- Dark theme: dark card, colored left border per level (red/amber/green).
- [✕] button dismisses the alert.
- Click on an alert → expands to show details (individual invoices, products, etc.).
- If no alerts → show "✅ No issues — everything looks good!"

### Important rules:
- Alerts are READ-ONLY observations. They do NOT automatically take action (no auto-sending emails). They INFORM the user, who then decides what to do.
- The user can then say "overdue invoices ke customers ko reminder bhejo" — and the existing bulk email flow handles it.
- Alerts should never crash the system — if a check fails, skip it and show the others.
- Log: `[ALERTS] 3 active: 1 critical, 2 warning`.

---

## "Done" checklist

### P&L Calculator:
- [ ] **"June ka P&L dikhao"** → shows revenue, expenses (breakdown by category), net profit/loss, comparison with previous month.
- [ ] **Different periods work:** "is month", "last month", "Q1", "this year" — all return correct P&L.
- [ ] **Comparison shows trend:** "↑ 12% improvement" or "↓ 8% decline" vs previous period.
- [ ] **Only P&L, no extras:** does NOT generate PDF/graph/Excel unless user specifically asks.
- [ ] **Dashboard P&L card:** small profit/loss summary on the dashboard Business Overview section.
- [ ] **[TOOL CALLED] calculate_pnl** appears in terminal.

### Smart Alerts:
- [ ] **GET /api/alerts** returns current alerts (critical/warning/info).
- [ ] **Overdue invoices detected:** if any invoices are past due_date → critical alert.
- [ ] **Low stock detected:** if any product stock < 5 → warning alert.
- [ ] **Expense spike detected:** if any expense category jumped 30%+ → warning alert.
- [ ] **Dashboard shows alert banner** at the top — colored by level, dismissable, expandable.
- [ ] **Chat mentions alerts** on first message of session: "You have X alerts..."
- [ ] **No alerts = positive message:** "✅ No issues" on dashboard.
- [ ] **Alerts never crash the system** — one failing check doesn't break others.
- [ ] **POST /api/alerts/dismiss/{id}** works — dismissed alert disappears.

### Overall:
- [ ] All previous features still work (import, charts, auth, WhatsApp, etc.).
- [ ] AGI-CORE dark theme consistent.
- [ ] No regressions.

---

## How to verify

1. "June ka P&L dikhao" → clean breakdown with profit/loss + comparison. No PDF/graph.
2. "Is saal ka P&L" → full year aggregate.
3. "June vs July compare karo P&L" → side by side comparison.
4. Open /dashboard → alert banner shows any overdue invoices or low stock.
5. Dismiss an alert → it disappears. Refresh → stays dismissed.
6. Open chat fresh → first AI message mentions active alerts.
7. If no problems exist → dashboard shows "✅ No issues."
