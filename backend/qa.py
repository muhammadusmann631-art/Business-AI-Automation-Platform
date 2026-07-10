"""Phase 5 — deterministic Reviewer / QA + guardrails layer.

This is the quality gate that runs AFTER the Supervisor has a draft final
answer but BEFORE anything is returned to the user. It is intentionally NOT
an LLM agent: it is a set of plain Python functions + regex. Deterministic
means fast, cheap, predictable, and easy to test.

What it does:
1. Redacts PII / secrets from the draft answer (always, regardless of checks).
2. Runs a set of checks (completeness, data sanity, business rules) over the
   draft answer and the per-step tool results.
3. Returns a QAResult saying PASS/FAIL, with reasons, and — when a failure is
   plausibly transient — which step to retry.

Kept modular on purpose: add more checks to ``_CHECKS`` without touching the
wiring in main.py. Scope is Phase 5 only — no failure queue, no human
approval, no LLM review (those are later phases).
"""

import os
import re
from dataclasses import dataclass, field


@dataclass
class Finding:
    """One problem the reviewer found.

    fixable=True + step_index set means "re-running that step might fix this"
    (used to drive the single retry). fixable=False means "flag it to the user".
    """

    check: str
    reason: str
    fixable: bool = False
    step_index: int | None = None


@dataclass
class QAResult:
    answer: str  # the draft answer AFTER PII redaction
    findings: list[Finding] = field(default_factory=list)
    redactions: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.findings

    @property
    def fixable_step(self) -> int | None:
        """The first step a retry could plausibly fix, if any."""
        for f in self.findings:
            if f.fixable and f.step_index is not None:
                return f.step_index
        return None

    def warning_text(self) -> str:
        return "; ".join(f.reason for f in self.findings)


# --------------------------------------------------------------------------- #
# Check 3 — PII / sensitive data redaction
# --------------------------------------------------------------------------- #

# (label, pattern). Basic, common patterns only — Phase 5 does not need to be
# exhaustive. Order matters a little: more specific patterns first.
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Credit card: 4 groups of 4 digits, separated by space or dash.
    ("credit card", re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}[ -]\d{4}\b")),
    # SSN / national-id: XXX-XX-XXXX.
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # DB connection strings with embedded credentials.
    (
        "connection string",
        re.compile(r"\b(?:postgres|postgresql|mysql|mongodb|redis|amqp)://[^\s\"']+", re.I),
    ),
    # Inline credentials, e.g. password=hunter2 / pwd: secret.
    ("credential", re.compile(r"(?i)(?:password|passwd|pwd)\s*[=:]\s*\S+")),
    # OpenAI/Stripe-style secret keys and AWS access keys.
    ("API key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9]{16,}\b")),
    ("API key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    # Generic api_key/token/secret assignments with a long-ish value.
    (
        "token",
        re.compile(r"(?i)\b(?:api[_-]?key|token|secret)\b\s*[=:]\s*[A-Za-z0-9_\-\.]{16,}"),
    ),
]


def redact(text: str) -> tuple[str, list[str]]:
    """Replace any sensitive patterns with [REDACTED].

    Returns the cleaned text and the list of pattern labels that fired (for
    logging). Runs regardless of any other check outcome.
    """
    redactions: list[str] = []
    for label, pattern in _PII_PATTERNS:
        if pattern.search(text):
            text = pattern.sub("[REDACTED]", text)
            redactions.append(label)
    return text, redactions


# --------------------------------------------------------------------------- #
# Check 1 — Output completeness
# --------------------------------------------------------------------------- #

def check_completeness(answer: str, steps: list[str], step_results: list[str]) -> list[Finding]:
    findings: list[Finding] = []

    if steps and not step_results:
        findings.append(Finding("completeness", "plan produced no step results"))
        return findings

    if len(step_results) < len(steps):
        findings.append(
            Finding(
                "completeness",
                f"only {len(step_results)} of {len(steps)} plan steps executed",
            )
        )

    for i, raw in enumerate(step_results, 1):
        text = (raw or "").strip()
        low = text.lower()
        if not text:
            # Empty output is plausibly transient -> allow one retry.
            findings.append(
                Finding("completeness", f"step {i} produced an empty result", True, i)
            )
        elif "no sales data" in low or "no data available" in low:
            # Data genuinely missing; retry will not conjure it -> flag it.
            findings.append(
                Finding("completeness", f"step {i} returned no data for the request")
            )

    return findings


# --------------------------------------------------------------------------- #
# Check 2 — Data sanity
# --------------------------------------------------------------------------- #

def check_data_sanity(answer: str, steps: list[str], step_results: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    haystack = "\n".join(step_results) + "\n" + (answer or "")

    # Sales / totals / amounts should not be negative.
    for m in re.finditer(
        r"(?i)\b(?:sales|amount|total|revenue|profit)\b[^\d\-\n]*(-\d[\d,]*)", haystack
    ):
        findings.append(
            Finding("data-sanity", f"negative value where a non-negative one is expected: {m.group(1)}")
        )

    # Month numbers above 12 are impossible.
    if re.search(r"(?i)\bmonth\s+(?:1[3-9]|[2-9]\d)\b", haystack):
        findings.append(Finding("data-sanity", "invalid month number (>12) detected"))

    return findings


# --------------------------------------------------------------------------- #
# Check 4 — Business-rule compliance (basic)
# --------------------------------------------------------------------------- #

def check_business_rules(answer: str, steps: list[str], step_results: list[str]) -> list[Finding]:
    findings: list[Finding] = []

    for i, raw in enumerate(step_results, 1):
        text = raw or ""
        low = text.lower()

        # Email drafts must have a valid-looking recipient.
        if "email draft" in low:
            # [ \t]* not \s* — \s would swallow the newline and grab the next line.
            m = re.search(r"(?im)^[ \t]*to:[ \t]*(.*)$", text)
            to = (m.group(1).strip() if m else "")
            if not to:
                findings.append(
                    Finding("business-rule", f"step {i}: email draft missing 'to' field")
                )
            elif "@" not in to:
                findings.append(
                    Finding(
                        "business-rule",
                        f"step {i}: email draft has an invalid 'to' address ({to})",
                    )
                )

        # A generated report must be a real, non-empty file on disk.
        m = re.search(r"saved at\s+(.+?\.pdf)", text)
        if m:
            path = m.group(1).strip()
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                # Missing/empty file is plausibly a transient write hiccup.
                findings.append(
                    Finding("business-rule", f"step {i}: report PDF missing or empty", True, i)
                )

        # Safety net on top of the DB layer: a rejected write means enforcement
        # already caught something unsafe. Surface it, but it is not a failure
        # of the answer itself, so we only note it in the terminal (no finding).
        if "query rejected" in low:
            print(f"[QA] note: step {i} had a query rejected by read-only enforcement")

    return findings


# All checks, run in order. Add new ones here to extend QA without touching
# the wiring in main.py.
_CHECKS = (check_completeness, check_data_sanity, check_business_rules)


def pii_only(answer: str) -> str:
    """Phase 8 fast-track QA: PII redaction only.

    Simple routed requests run no tools, so completeness/data/business checks
    have nothing to inspect — but nothing may leave unredacted. Returns the
    cleaned answer.
    """
    print("[QA] checking output (PII only)...")
    redacted, redactions = redact(answer or "")
    for label in redactions:
        print(f"[QA] REDACTED: {label}")
    print("[QA] PASS")
    return redacted


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def review(
    answer: str,
    step_results: list[str],
    steps: list[str],
    tool_failures: list[dict] | None = None,
) -> QAResult:
    """Inspect a draft answer + its step results. Returns a QAResult.

    Always redacts PII first (and logs it). Then runs every check. A check
    that raises is logged and skipped so QA can never crash the request.

    ``tool_failures`` (Phase 6) is a list of tool calls that failed even after
    retry/dead-lettering. They are surfaced deterministically as findings —
    independent of whether the LLM relayed the failure text — so the user is
    always warned that part of the request could not be completed.
    """
    print("[QA] checking output...")

    redacted, redactions = redact(answer or "")
    for label in redactions:
        print(f"[QA] REDACTED: {label}")

    findings: list[Finding] = []
    seen: set[str] = set()
    for check in _CHECKS:
        try:
            for f in check(redacted, steps, step_results):
                if f.reason not in seen:  # collapse duplicates (answer + results)
                    seen.add(f.reason)
                    findings.append(f)
        except Exception as e:  # a buggy check must not break the response
            print(f"[QA] check {check.__name__} errored (ignored): {e}")

    # Phase 6 tool failures -> non-fixable findings (already retried upstream).
    for tf in tool_failures or []:
        attempts = tf.get("attempts", "?")
        reason = (
            f"the '{tf.get('tool', 'unknown')}' step could not be completed "
            f"after {attempts} attempt(s) and was logged for review"
        )
        if reason not in seen:
            seen.add(reason)
            findings.append(Finding("tool-failure", reason))

    result = QAResult(answer=redacted, findings=findings, redactions=redactions)

    if result.passed:
        print("[QA] PASS")
    else:
        for f in result.findings:
            print(f"[QA] FAIL: {f.reason}")

    return result


if __name__ == "__main__":
    # Standalone smoke test — no OpenAI / server needed.
    print("--- PII redaction ---")
    r = review(
        "Your card 4111-1111-1111-1111 and SSN 123-45-6789 are on file.",
        step_results=["Sales for June were 45000."],
        steps=["look up June sales"],
    )
    print("answer:", r.answer, "| passed:", r.passed)

    print("\n--- empty data (fixable retry) ---")
    r = review("...", step_results=[""], steps=["look up sales"])
    print("fixable_step:", r.fixable_step)

    print("\n--- bad email + no data ---")
    r = review(
        "Here is your draft.",
        step_results=[
            "EMAIL DRAFT (not sent):\nTo: not-an-address\nSubject: Hi\n\nBody",
            "No sales data available for Smarch.",
        ],
        steps=["draft email", "look up sales"],
    )
    print("passed:", r.passed, "| warnings:", r.warning_text())
