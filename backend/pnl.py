"""Batch 2 — Profit & Loss calculator (deterministic: pure SQL + math).

Revenue comes from the `sales` table (keyed by month name); expenses from the
`expenses` table (keyed by real dates). Supports flexible periods — a month,
current/last month, a quarter, or the full year — with a comparison against
the previous period.
"""

from datetime import datetime

import database as db

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_QUARTERS = {
    "q1": [0, 1, 2], "q2": [3, 4, 5], "q3": [6, 7, 8], "q4": [9, 10, 11],
}


def _month_nums(indices: list[int]) -> list[str]:
    return [f"{i + 1:02d}" for i in indices]


def _resolve(period: str) -> tuple[str, list[int]]:
    """Return (label, list of 0-based month indices) for a period string."""
    p = (period or "").strip().lower()
    now_idx = datetime.now().month - 1

    if p in ("", "current_month", "current month", "this month", "is month", "current"):
        return (MONTHS[now_idx], [now_idx])
    if p in ("last_month", "previous month", "pichle month", "last month", "pichlay month"):
        return (MONTHS[(now_idx - 1) % 12], [(now_idx - 1) % 12])
    for qk, idxs in _QUARTERS.items():
        if qk in p or (qk == "q1" and "pehli quarter" in p):
            return (qk.upper(), idxs)
    if "year" in p or "saal" in p or (p.isdigit() and len(p) == 4):
        return ("This Year", list(range(12)))
    for i, m in enumerate(MONTHS):
        if m.lower() in p or m.lower()[:3] in p.split():
            return (m, [i])
    return (MONTHS[now_idx], [now_idx])  # default: current month


def _prev_indices(indices: list[int]) -> list[int]:
    if len(indices) >= 12:
        return []  # full year -> no previous-period data in this dataset
    shift = len(indices)
    return [(i - shift) % 12 for i in indices]


def _revenue(indices: list[int]) -> float:
    if not indices:
        return 0.0
    names = [MONTHS[i] for i in indices]
    placeholders = ", ".join("?" for _ in names)
    rows = db.run_select(
        f"SELECT SUM(amount) AS total FROM sales WHERE month IN ({placeholders})", tuple(names)
    )
    return float(rows[0]["total"] or 0) if rows else 0.0


def _expenses(indices: list[int]) -> tuple[float, list[dict]]:
    if not indices:
        return 0.0, []
    nums = _month_nums(indices)
    placeholders = ", ".join("?" for _ in nums)
    rows = db.run_select(
        f"SELECT category, SUM(amount) AS total FROM expenses "
        f"WHERE strftime('%m', date) IN ({placeholders}) GROUP BY category "
        f"ORDER BY total DESC",
        tuple(nums),
    )
    breakdown = [{"category": r["category"], "total": float(r["total"] or 0)} for r in rows]
    return sum(b["total"] for b in breakdown), breakdown


def calculate_pnl(period: str = "current_month") -> dict:
    """Compute P&L for a period with a previous-period comparison."""
    label, indices = _resolve(period)
    revenue = _revenue(indices)
    total_expenses, breakdown = _expenses(indices)
    net = revenue - total_expenses

    prev_idx = _prev_indices(indices)
    prev_revenue = _revenue(prev_idx)
    prev_expenses, _ = _expenses(prev_idx)
    prev_net = prev_revenue - prev_expenses
    if prev_net:
        change_pct = round((net - prev_net) / abs(prev_net) * 100, 1)
    else:
        change_pct = 0.0
    prev_label = MONTHS[prev_idx[0]] if len(prev_idx) == 1 else ("—" if not prev_idx else "prev period")

    return {
        "period": label,
        "revenue": round(revenue, 2),
        "expenses": {"total": round(total_expenses, 2), "breakdown": breakdown},
        "net": round(net, 2),
        "status": "PROFIT" if net >= 0 else "LOSS",
        "comparison": {
            "previous_period": prev_label,
            "previous_net": round(prev_net, 2),
            "change_percent": change_pct,
            "trend": "UP" if change_pct > 0 else ("DOWN" if change_pct < 0 else "FLAT"),
        },
    }


def format_pnl(pnl: dict) -> str:
    """Render a clean text P&L block (for the agent / WhatsApp)."""
    lines = [f"{pnl['period']} — Profit & Loss", ""]
    lines.append(f"Revenue:   ${pnl['revenue']:,.0f}")
    lines.append(f"Expenses:  ${pnl['expenses']['total']:,.0f}")
    for b in pnl["expenses"]["breakdown"]:
        lines.append(f"  - {b['category'].title()}: ${b['total']:,.0f}")
    icon = "PROFIT" if pnl["status"] == "PROFIT" else "LOSS"
    lines.append(f"Net {icon}: ${pnl['net']:,.0f}")
    c = pnl["comparison"]
    if c["previous_net"]:
        arrow = "up" if c["trend"] == "UP" else "down"
        lines.append(f"vs {c['previous_period']}: {arrow} {abs(c['change_percent'])}% "
                     f"(${c['previous_net']:,.0f} -> ${pnl['net']:,.0f})")
    return "\n".join(lines)


if __name__ == "__main__":
    db.seed()
    for p in ("June", "current_month", "last month", "Q2", "this year"):
        r = calculate_pnl(p)
        print(f"{p:14} -> {r['status']} net=${r['net']:,.0f} "
              f"(rev ${r['revenue']:,.0f} exp ${r['expenses']['total']:,.0f}) "
              f"vs {r['comparison']['previous_period']} {r['comparison']['change_percent']}%")
