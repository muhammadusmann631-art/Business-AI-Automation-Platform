"""Batch 2 — Smart Alerts: proactive checks on the business data.

Each check is independent and wrapped so one failure never blocks the others.
Results are cached for 5 minutes (avoid running every query on each page load)
and can be dismissed (hidden until the same alert triggers again).
"""

import hashlib
import time
from dataclasses import dataclass, field

import database as db

_LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}
_CACHE_TTL = 300  # seconds
_cache: dict = {"time": 0.0, "alerts": []}
_dismissed: set[str] = set()


@dataclass
class Alert:
    level: str          # critical | warning | info
    message: str
    details: list = field(default_factory=list)

    @property
    def id(self) -> str:
        # Stable id from level+message so a dismissal sticks until the alert
        # content changes (i.e. the situation changes).
        return hashlib.md5(f"{self.level}:{self.message}".encode()).hexdigest()[:10]

    def to_dict(self) -> dict:
        return {"id": self.id, "level": self.level, "message": self.message, "details": self.details}


def _q(sql: str, params: tuple = ()) -> list[dict]:
    return db.run_select(sql, params)


# ------------------------------- the 6 checks ------------------------------ #
def check_overdue_invoices() -> list[Alert]:
    rows = _q(
        "SELECT i.invoice_number AS num, i.amount AS amount, "
        "COALESCE(c.name,'?') AS customer FROM invoices i "
        "LEFT JOIN customers c ON i.customer_id=c.id "
        "WHERE i.status='overdue' OR (i.status='pending' AND i.due_date < date('now')) "
        "ORDER BY i.amount DESC"
    )
    if not rows:
        return []
    total = sum(float(r["amount"] or 0) for r in rows)
    return [Alert("critical", f"{len(rows)} invoices overdue (total: ${total:,.0f})",
                  [f"{r['num']}: ${float(r['amount']):,.0f} — {r['customer']}" for r in rows])]


def check_low_stock(threshold: int = 5) -> list[Alert]:
    rows = _q("SELECT name, stock FROM products WHERE stock < ? AND status='active' ORDER BY stock",
              (threshold,))
    if not rows:
        return []
    return [Alert("warning", f"{len(rows)} product(s) have low stock",
                  [f"{r['name']}: {r['stock']} remaining" for r in rows])]


def check_expense_spike(threshold_pct: int = 30) -> list[Alert]:
    # Compare the two most recent months that have expense data, per category.
    months = _q("SELECT DISTINCT strftime('%m', date) AS m FROM expenses ORDER BY m DESC")
    if len(months) < 2:
        return []
    cur, prev = months[0]["m"], months[1]["m"]
    cur_rows = {r["category"]: float(r["total"] or 0) for r in _q(
        "SELECT category, SUM(amount) AS total FROM expenses WHERE strftime('%m',date)=? GROUP BY category", (cur,))}
    prev_rows = {r["category"]: float(r["total"] or 0) for r in _q(
        "SELECT category, SUM(amount) AS total FROM expenses WHERE strftime('%m',date)=? GROUP BY category", (prev,))}
    spikes = []
    for cat, now_val in cur_rows.items():
        before = prev_rows.get(cat, 0)
        if before and (now_val - before) / before * 100 >= threshold_pct:
            pct = (now_val - before) / before * 100
            spikes.append(f"{cat.title()}: up {pct:.0f}% (${before:,.0f} -> ${now_val:,.0f})")
    if not spikes:
        return []
    return [Alert("warning", f"{len(spikes)} expense categor(y/ies) spiked 30%+", spikes)]


def check_approaching_dues(days: int = 3) -> list[Alert]:
    rows = _q(
        "SELECT invoice_number AS num, amount, due_date FROM invoices "
        "WHERE status='pending' AND due_date BETWEEN date('now') AND date('now', ?) "
        "ORDER BY due_date", (f"+{days} days",))
    if not rows:
        return []
    return [Alert("warning", f"{len(rows)} invoice(s) due within {days} days",
                  [f"{r['num']}: ${float(r['amount']):,.0f} due {r['due_date']}" for r in rows])]


def check_inactive_customers() -> list[Alert]:
    rows = _q(
        "SELECT name FROM customers WHERE status='active' AND id NOT IN "
        "(SELECT customer_id FROM sales WHERE customer_id IS NOT NULL) ORDER BY name LIMIT 10")
    if not rows:
        return []
    return [Alert("info", f"{len(rows)} active customer(s) have no recorded sales",
                  [r["name"] for r in rows])]


def check_milestones() -> list[Alert]:
    rows = _q("SELECT month, amount FROM sales ORDER BY amount DESC LIMIT 1")
    if not rows:
        return []
    top = rows[0]
    return [Alert("info", f"Best month: {top['month']} with ${float(top['amount']):,.0f} in sales")]


_CHECKS = [
    check_overdue_invoices, check_low_stock, check_expense_spike,
    check_approaching_dues, check_inactive_customers, check_milestones,
]


def run_all_checks() -> list[Alert]:
    """Run every check (independently) and return alerts, critical first."""
    alerts: list[Alert] = []
    for check in _CHECKS:
        try:
            alerts.extend(check())
        except Exception as e:
            print(f"[ALERTS] check {check.__name__} failed (skipped): {e}")
    alerts.sort(key=lambda a: _LEVEL_ORDER.get(a.level, 9))
    return alerts


def get_alerts(force: bool = False) -> list[dict]:
    """Cached (5 min) list of non-dismissed alerts as dicts."""
    now = time.monotonic()
    if force or now - _cache["time"] > _CACHE_TTL:
        _cache["alerts"] = run_all_checks()
        _cache["time"] = now
    active = [a for a in _cache["alerts"] if a.id not in _dismissed]
    crit = sum(1 for a in active if a.level == "critical")
    warn = sum(1 for a in active if a.level == "warning")
    print(f"[ALERTS] {len(active)} active: {crit} critical, {warn} warning")
    return [a.to_dict() for a in active]


def dismiss(alert_id: str) -> None:
    _dismissed.add(alert_id)


def alert_summary_text() -> str:
    """Short text list of active alerts for the chat welcome / WhatsApp."""
    active = [a for a in _cache["alerts"] if a.id not in _dismissed] or run_all_checks()
    active = [a for a in active if a.id not in _dismissed]
    if not active:
        return ""
    icon = {"critical": "🔴", "warning": "🟡", "info": "🟢"}
    lines = [f"{icon.get(a.level, '•')} {a.message}" for a in active]
    return "\n".join(lines)


if __name__ == "__main__":
    db.seed()
    for a in get_alerts(force=True):
        print(a["level"].upper(), "-", a["message"], "|", len(a["details"]), "details")
