"""Batch 3 — bulk operations: act on MANY items behind ONE human approval.

A bulk operation bundles N individual actions (send N emails, update N rows)
plus a callable that executes them all. It is parked in an in-memory store
until the user approves or rejects — mirroring the Phase 7 single-approval
model, but for a whole batch.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

TTL_SECONDS = 10 * 60


@dataclass
class BulkOperation:
    bulk_id: str
    action: str            # send_email | update_status | update_price
    total_count: int
    preview: list          # first few items shown to the user
    risk_reason: str
    session_id: str
    execute_fn: Callable[[], dict]  # runs all items -> {success, failed, total}
    created_at: float = field(default_factory=time.monotonic)


_PENDING: dict[str, BulkOperation] = {}


class BulkNotFound(KeyError):
    """Unknown, already-decided, or expired bulk operation."""


def _purge() -> None:
    now = time.monotonic()
    for bid in [b for b, op in _PENDING.items() if now - op.created_at > TTL_SECONDS]:
        _PENDING.pop(bid, None)
        print(f"[BULK] expired: {bid}")


def create(action: str, total_count: int, preview: list, risk_reason: str,
           session_id: str, execute_fn: Callable[[], dict]) -> BulkOperation:
    _purge()
    op = BulkOperation(
        bulk_id="bulk-" + uuid.uuid4().hex[:8],
        action=action,
        total_count=total_count,
        preview=preview,
        risk_reason=risk_reason,
        session_id=session_id,
        execute_fn=execute_fn,
    )
    _PENDING[op.bulk_id] = op
    print(f"[BULK] prepared: {total_count} {action} ({op.bulk_id})")
    return op


def approve(bulk_id: str) -> dict:
    _purge()
    op = _PENDING.pop(bulk_id, None)
    if op is None:
        raise BulkNotFound(bulk_id)
    print(f"[BULK] approved: {bulk_id} — executing {op.total_count} items")
    result = op.execute_fn()
    print(f"[BULK] completed: {result['success']}/{result['total']} success, "
          f"{result['failed']} failed")
    result["action"] = op.action
    return result


def reject(bulk_id: str) -> BulkOperation:
    _purge()
    op = _PENDING.pop(bulk_id, None)
    if op is None:
        raise BulkNotFound(bulk_id)
    print(f"[BULK] rejected: {bulk_id} — cancelled")
    return op


def payload(op: BulkOperation) -> dict:
    """The pending_bulk_approval object sent to the frontend."""
    return {
        "bulk_id": op.bulk_id,
        "action": op.action,
        "total_count": op.total_count,
        "preview": op.preview,
        "remaining": max(0, op.total_count - len(op.preview)),
        "risk_reason": op.risk_reason,
    }
