"""Phase 6 — retry-with-backoff wrapper + transient/permanent classification.

A small, reusable resilience layer. Wrap any (sync) callable with
``call_with_retry`` and it will:
  - retry on TRANSIENT errors with exponential backoff (1s, 2s, 4s),
  - fail IMMEDIATELY on PERMANENT errors (no retries),
  - raise ``RetryExhausted`` once all attempts are spent, carrying the last
    error and the attempt count so the caller can dead-letter it.

Kept separate from the agent code so every tool — now and in later phases —
gets the same protection just by going through this wrapper.

Scope note (Phase 6): no real message queue, no async scheduler. Plain
blocking backoff is enough to prove the pattern.
"""

import time

DEFAULT_MAX_RETRIES = 3          # 1 initial try + 3 retries = 4 attempts total
DEFAULT_BASE_DELAY = 1.0         # seconds; doubles each retry (1 -> 2 -> 4)

# Swappable so tests don't actually sleep. Referenced as a module global at
# call time, so reassigning resilience._sleep in a test takes effect.
_sleep = time.sleep


class PermanentError(Exception):
    """Explicitly non-retryable. Fails immediately."""


class TransientError(Exception):
    """Explicitly retryable."""


class RetryExhausted(Exception):
    """Raised when a transient failure survives all retries."""

    def __init__(self, tool_name: str, attempts: int, last_error: Exception):
        self.tool_name = tool_name
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"{tool_name} failed after {attempts} attempts: {last_error}"
        )


# Substrings that mark an error as transient (recoverable) or permanent.
# Permanent is checked first so an "invalid ... timeout" reads as permanent.
_PERMANENT_HINTS = (
    "invalid", "syntax", "unsafe", "read-only", "not allowed",
    "missing required", "required parameter", "bad request", "400",
    "authentication", "unauthorized", "forbidden", "permission denied",
    "not found",
)
_TRANSIENT_HINTS = (
    "timeout", "timed out", "connection refused", "connection reset",
    "connection error", "temporarily unavailable", "temporarily",
    "too many connections", "database is locked", "deadlock",
    "rate limit", "429", "500", "502", "503", "disk busy", "try again",
)


def is_transient(err: Exception) -> bool:
    """Classify an error. Default to TRANSIENT when uncertain.

    Rationale (from the skill): retrying an unrecoverable task wastes a few
    seconds; NOT retrying a recoverable one loses work. So bias to retry.
    """
    if isinstance(err, PermanentError):
        return False
    if isinstance(err, TransientError):
        return True
    if isinstance(err, (TimeoutError, ConnectionError)):
        return True
    # ValueError/TypeError usually mean bad input -> permanent.
    if isinstance(err, (ValueError, TypeError, KeyError)):
        return False

    msg = str(err).lower()
    if any(h in msg for h in _PERMANENT_HINTS):
        return False
    if any(h in msg for h in _TRANSIENT_HINTS):
        return True
    return True  # uncertain -> retry


def call_with_retry(
    func,
    *args,
    tool_name: str = "tool",
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    **kwargs,
):
    """Call ``func(*args, **kwargs)`` with backoff on transient errors.

    Returns the function's result on success. Raises the original error on a
    permanent failure, or ``RetryExhausted`` when transient retries run out.
    """
    attempts = max_retries + 1
    for attempt in range(1, attempts + 1):
        try:
            result = func(*args, **kwargs)
            if attempt > 1:
                print(f"[RETRY] recovered on attempt {attempt}/{attempts} for {tool_name}")
            return result
        except Exception as e:
            if not is_transient(e):
                # Permanent: do not retry, surface immediately.
                raise
            if attempt < attempts:
                wait = base_delay * (2 ** (attempt - 1))
                print(
                    f"[RETRY] attempt {attempt + 1}/{attempts} for {tool_name} "
                    f"after {wait:g}s — reason: {e}"
                )
                _sleep(wait)
            else:
                # Out of attempts: hand the caller enough to dead-letter it.
                raise RetryExhausted(tool_name, attempts, e) from e


if __name__ == "__main__":
    # Standalone smoke test — no server needed. Use a no-op sleep so it's fast.
    _sleep = lambda s: None  # noqa: E731

    print("--- transient, recovers on 3rd attempt ---")
    box = {"n": 0}

    def flaky():
        box["n"] += 1
        if box["n"] < 3:
            raise TimeoutError("connection timed out")
        return "ok"

    print("result:", call_with_retry(flaky, tool_name="flaky"))

    print("\n--- transient, exhausts ---")
    def always_down():
        raise ConnectionError("connection refused")

    try:
        call_with_retry(always_down, tool_name="always_down")
    except RetryExhausted as e:
        print("RetryExhausted:", e, "| attempts:", e.attempts)

    print("\n--- permanent, no retry ---")
    def bad_input():
        raise ValueError("invalid query syntax")

    try:
        call_with_retry(bad_input, tool_name="bad_input")
    except ValueError as e:
        print("raised immediately (no retry):", e)
