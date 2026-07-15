"""Phase 8 — smart router: SIMPLE (fast track) vs COMPLEX (full pipeline).

Classifies every incoming request BEFORE it enters the heavy
Supervisor/Planner/tools pipeline:

- Obvious complexity signals (report/email/sales/months/...) are caught by
  free regex rules — no API call at all.
- A short referential message ("now summarize that") after earlier tool/data
  work is COMPLEX — it needs the prior context.
- Everything else goes to ONE tiny, cheap LLM classification call
  (gpt-4o-mini, prompt well under 200 tokens), whose verdict is cached per
  message.
- Any uncertainty or classifier error defaults to COMPLEX: over-processing a
  greeting is cheap; under-processing a tool request loses work.
"""

import re

from openai import AsyncOpenAI

SIMPLE = "simple"
COMPLEX = "complex"

# ----------------------------------------------------------------- rules -- #

# Anything that smells like data, documents, email, or multi-step business
# work. Month names imply a sales/data lookup in this system.
_COMPLEX_SIGNALS = re.compile(
    r"(?i)\b(report|pdf|excel|xlsx|email|send|bhej|mail|draft|sales|revenue|profit|"
    r"total|data(base)?|sql|query|analy[sz]e|compare|export|chart|graph|"
    r"summar(y|ise|ize)|preference|always|from now on|"
    # business tables / entities (Level 1)
    r"customer|client|invoice|bill|product|stock|inventory|expense|kharch|"
    r"overdue|pending|paid|revenue|p&l|pnl|profit|loss|financial|kamaya|kamai|"
    r"alert|import|"
    r"january|february|march|april|may|june|july|august|september|october|"
    r"november|december|force_fail)\b"
)

# Words that refer back to earlier work ("summarize that", "email it").
_REFERENTIAL = re.compile(r"(?i)\b(that|it|this|those|them|again|previous|earlier|above)\b")

# Traces that earlier turns involved tools/data (from the stored history).
_HISTORY_COMPLEX_MARKERS = ("pdf report", "email draft", "sales for", "preference saved")

# Cache LLM verdicts so a repeated message costs nothing the second time.
_cache: dict[str, str] = {}

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


_CLASSIFIER_SYSTEM = (
    "Classify the user request as SIMPLE or COMPLEX. "
    "SIMPLE = answerable directly with no tools, no data lookup, no file "
    "generation, no multi-step work (greetings, general knowledge, quick "
    "math, opinions, definitions). "
    "COMPLEX = needs database queries, reports, emails, saved preferences, "
    "multi-step analysis, or refers to earlier data/tool results. "
    "If unsure, answer COMPLEX. Reply with exactly one word: SIMPLE or COMPLEX."
)


async def classify(message: str, history_text: str = "") -> tuple[str, str]:
    """Return ("simple"|"complex", reason). Never raises — errors → COMPLEX."""
    msg = (message or "").strip()

    # Rule 1: explicit complexity signals — free and certain.
    if _COMPLEX_SIGNALS.search(msg):
        reason = "requires data lookup/report/email/tool work"
        print(f"[ROUTER] COMPLEX — full pipeline (reason: {reason})")
        return COMPLEX, reason

    # Rule 2: refers back to earlier tool/data work — needs that context.
    low_history = history_text.lower()
    if _REFERENTIAL.search(msg) and any(m in low_history for m in _HISTORY_COMPLEX_MARKERS):
        reason = "refers to earlier data/tool results"
        print(f"[ROUTER] COMPLEX — full pipeline (reason: {reason})")
        return COMPLEX, reason

    # Cached LLM verdict?
    key = msg.lower()
    if key in _cache:
        decision = _cache[key]
        reason = "cached classification"
        label = "SIMPLE — fast track" if decision == SIMPLE else "COMPLEX — full pipeline"
        print(f"[ROUTER] {label} (reason: {reason})")
        return decision, reason

    # LLM classification: one tiny, cheap call.
    try:
        resp = await _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _CLASSIFIER_SYSTEM},
                {"role": "user", "content": msg[:500]},
            ],
            max_tokens=2,
            temperature=0,
        )
        word = (resp.choices[0].message.content or "").strip().upper()
    except Exception as e:
        print(f"[ROUTER] UNCERTAIN — defaulting to COMPLEX (classifier error: {e})")
        return COMPLEX, "classifier error — safe default"

    if word.startswith("SIMPLE"):
        _cache[key] = SIMPLE
        reason = "greeting/general knowledge — no tools needed"
        print(f"[ROUTER] SIMPLE — fast track (reason: {reason})")
        return SIMPLE, reason
    if word.startswith("COMPLEX"):
        _cache[key] = COMPLEX
        reason = "classifier judged multi-step/tool work"
        print(f"[ROUTER] COMPLEX — full pipeline (reason: {reason})")
        return COMPLEX, reason

    print(f"[ROUTER] UNCERTAIN — defaulting to COMPLEX (unexpected verdict: {word!r})")
    return COMPLEX, "unclear classification — safe default"


# --------------------------------------------------------- cost estimator -- #

_TOTAL = {"tokens": 0}


def log_cost(kind: str, *texts: str, overhead: int = 0) -> int:
    """Log a rough token estimate (chars/4 + per-call overhead). Not billing —
    just makes the simple-vs-complex saving visible in the terminal."""
    approx = overhead + sum(len(t) for t in texts if t) // 4
    _TOTAL["tokens"] += approx
    print(f"[COST] ~{approx} tokens ({kind}) — running total ~{_TOTAL['tokens']}")
    return approx


if __name__ == "__main__":
    # Offline smoke test of the FREE rule paths (no API call needed).
    import asyncio

    async def t():
        d, r = await classify("get June sales and make a PDF report")
        assert d == COMPLEX, r
        d, r = await classify("email the summary to the client")
        assert d == COMPLEX, r
        d, r = await classify("now summarize that", "Assistant: PDF report created: http://x/y.pdf")
        assert d == COMPLEX, r
        d, r = await classify("tell me about our sales")
        assert d == COMPLEX, r
        print("rule paths OK (LLM path needs a live key)")

    asyncio.run(t())
    log_cost("simple fast-track", "x" * 800, overhead=100)
    log_cost("full pipeline", "x" * 8000, overhead=1000)
