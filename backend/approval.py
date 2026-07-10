"""Phase 7 — human-in-the-loop approval: risk classifier + pending store.

Two things live here:

1. ``classify_risk(action, context)`` — a RULE-BASED (never LLM) classifier
   that decides whether an action executes automatically or must pause for
   explicit human approval. Rules are plain ``if``s so they are predictable
   and easy to update.

2. The pending-approval store — an in-memory dict of actions waiting for a
   human decision. Each entry holds the full action details (so the human
   sees exactly what will happen) plus the callable to execute on approval.
   Entries expire after ``TTL_SECONDS`` with no decision.

Phase 7 scope: in-memory only (no DB), no RBAC (any user may approve), and
approval happens in the chat UI only — no Slack/email/push.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

TTL_SECONDS = 10 * 60  # pending approvals expire after 10 minutes

REQUIRES_APPROVAL = "requires_approval"
AUTO = "auto"

# Actions that are always high-risk. Everything not matched by a rule below
# defaults to AUTO — reads, drafts, summaries, chat.
_HIGH_RISK_ACTIONS = {
    "send_email": "sending an email to an external recipient",
    "final_report": "finalising a report for external sharing",
    "data_export": "large data export",
}


def classify_risk(action: str, context: dict | None = None) -> str:
    """Classify an action as ``requires_approval`` or ``auto``. Rule-based.

    Context flags (all optional):
      - ``needs_approval``: explicit flag from the Planner/Supervisor —
        catch-all for actions the agent itself is uncertain about.
      - ``qa_warning``: the output was flagged by the Phase 5 QA layer —
        flagged work must not auto-execute.
      - ``external``: the result leaves the company (e.g. a report marked
        for a client) — treat as final_report-grade risk.
    """
    context = context or {}
    reason = None

    if action in _HIGH_RISK_ACTIONS:
        reason = _HIGH_RISK_ACTIONS[action]
    elif context.get("needs_approval"):
        reason = "explicitly marked as needing approval"
    elif context.get("qa_warning"):
        reason = "output was flagged by QA review"
    elif context.get("external"):
        reason = "result is intended for an external party"

    if reason:
        print(f"[RISK] action: {action} -> requires_approval (reason: {reason})")
        return REQUIRES_APPROVAL
    # Low-risk: keep the terminal clean — no log for the common case.
    return AUTO


def risk_reason(action: str, context: dict | None = None) -> str:
    """Human-readable reason shown on the approval card."""
    context = context or {}
    if action in _HIGH_RISK_ACTIONS:
        return _HIGH_RISK_ACTIONS[action]
    if context.get("needs_approval"):
        return "explicitly marked as needing approval"
    if context.get("qa_warning"):
        return "output was flagged by QA review"
    if context.get("external"):
        return "result is intended for an external party"
    return "high-risk action"


# --------------------------------------------------------------------------- #
# Pending approval store
# --------------------------------------------------------------------------- #

@dataclass
class Pending:
    approval_id: str
    action: str
    details: dict            # full draft/details the human must see
    execute: Callable[[], str]  # runs ONLY on approval; returns a result message
    session_id: str
    risk_reason: str
    created_at: float = field(default_factory=time.monotonic)


_PENDING: dict[str, Pending] = {}


class ApprovalNotFound(KeyError):
    """Unknown, already-decided, or expired approval_id."""


def _purge_expired() -> None:
    """Drop pendings older than the TTL. Called on every store access —
    good enough for an in-memory Phase 7 store; no background thread needed."""
    now = time.monotonic()
    for aid in [a for a, p in _PENDING.items() if now - p.created_at > TTL_SECONDS]:
        p = _PENDING.pop(aid)
        print(f"[APPROVAL] expired: {p.action} (id: {aid}) — no decision within timeout")


def create_pending(
    action: str,
    details: dict,
    execute: Callable[[], str],
    session_id: str,
    reason: str = "",
) -> Pending:
    """Park a high-risk action until a human decides. Returns the entry."""
    _purge_expired()
    approval_id = uuid.uuid4().hex[:12]
    entry = Pending(
        approval_id=approval_id,
        action=action,
        details=details,
        execute=execute,
        session_id=session_id,
        risk_reason=reason or risk_reason(action),
    )
    _PENDING[approval_id] = entry
    print(f"[PENDING] created approval {approval_id} for {action} — waiting for human decision")
    return entry


def approve(approval_id: str) -> str:
    """Execute a pending action. Removes it from the store either way."""
    _purge_expired()
    entry = _PENDING.pop(approval_id, None)
    if entry is None:
        raise ApprovalNotFound(approval_id)
    print(f"[APPROVAL] approved: {entry.action} (id: {approval_id}) — executing now")
    return entry.execute()


def reject(approval_id: str) -> Pending:
    """Cancel a pending action without executing it."""
    _purge_expired()
    entry = _PENDING.pop(approval_id, None)
    if entry is None:
        raise ApprovalNotFound(approval_id)
    print(f"[APPROVAL] rejected: {entry.action} (id: {approval_id}) — action cancelled")
    return entry


def pending_count() -> int:
    _purge_expired()
    return len(_PENDING)


if __name__ == "__main__":
    # Standalone smoke test — no server needed.
    print("--- classifier ---")
    assert classify_risk("send_email") == REQUIRES_APPROVAL
    assert classify_risk("query_sales") == AUTO
    assert classify_risk("summarise") == AUTO
    assert classify_risk("generate_report", {"external": True}) == REQUIRES_APPROVAL
    assert classify_risk("anything", {"needs_approval": True}) == REQUIRES_APPROVAL
    assert classify_risk("anything", {"qa_warning": True}) == REQUIRES_APPROVAL
    print("classifier OK")

    print("\n--- approve path ---")
    p = create_pending(
        "send_email",
        {"to": "client@acme.com", "subject": "Hi", "body": "..."},
        lambda: "email sent!",
        "sess-1",
    )
    print("result:", approve(p.approval_id))

    print("\n--- reject path ---")
    p = create_pending("send_email", {"to": "x@y.z"}, lambda: "never runs", "sess-1")
    reject(p.approval_id)

    print("\n--- unknown id ---")
    try:
        approve("nope")
    except ApprovalNotFound:
        print("ApprovalNotFound raised OK")

    print("\n--- expiry ---")
    p = create_pending("send_email", {"to": "x@y.z"}, lambda: "never runs", "sess-1")
    _PENDING[p.approval_id].created_at -= TTL_SECONDS + 1  # simulate old entry
    assert pending_count() == 0  # purge ran and logged expiry
    print("expiry OK")
