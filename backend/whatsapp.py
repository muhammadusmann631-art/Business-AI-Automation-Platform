"""WhatsApp channel via Twilio.

Sends replies and validates incoming webhooks. Credentials come from the
environment; if they are missing the module degrades gracefully (the webhook
returns a clear "not configured" message instead of crashing).
"""

import os
import re

WA_LIMIT = 1500  # WhatsApp hard limit is 1600 chars/msg; leave headroom.


def _sid() -> str | None:
    return os.getenv("TWILIO_ACCOUNT_SID")


def _token() -> str | None:
    return os.getenv("TWILIO_AUTH_TOKEN")


def _number() -> str | None:
    return os.getenv("TWILIO_WHATSAPP_NUMBER")


def is_configured() -> bool:
    return bool(_sid() and _token() and _number())


def to_plain(text: str) -> str:
    """Strip markdown/HTML so the message reads cleanly in WhatsApp."""
    text = text or ""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", text)  # [label](url) -> label: url
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)               # bold
    text = re.sub(r"`([^`]+)`", r"\1", text)                      # inline code
    text = re.sub(r"<[^>]+>", "", text)                           # any HTML tags
    return text.strip()


def split_message(text: str, limit: int = WA_LIMIT) -> list[str]:
    """Split a long reply into WhatsApp-sized chunks on paragraph/line breaks."""
    text = text or ""
    if len(text) <= limit:
        return [text] if text else []
    chunks, current = [], ""
    for para in text.split("\n"):
        if len(current) + len(para) + 1 > limit:
            if current:
                chunks.append(current)
            # a single very long line still needs hard slicing
            while len(para) > limit:
                chunks.append(para[:limit])
                para = para[limit:]
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def validate_signature(url: str, params: dict, signature: str | None) -> bool:
    """Verify the request really came from Twilio. In dev (no token) allow it."""
    token = _token()
    if not token:
        return True
    try:
        from twilio.request_validator import RequestValidator

        return RequestValidator(token).validate(url, params, signature or "")
    except Exception:
        return False


def send_reply(to_number: str, message: str) -> bool:
    """Send a (possibly multi-part) WhatsApp reply. Returns True if sent."""
    if not is_configured():
        print("[WHATSAPP] send skipped — not configured")
        return False
    try:
        from twilio.rest import Client

        client = Client(_sid(), _token())
        for chunk in split_message(message) or [""]:
            client.messages.create(
                body=chunk,
                from_=f"whatsapp:{_number()}",
                to=f"whatsapp:{to_number}",
            )
        print(f"[WHATSAPP] sent to {to_number} ({len(split_message(message))} part(s))")
        return True
    except Exception as e:
        print(f"[WHATSAPP] send failed: {e}")
        return False


if __name__ == "__main__":
    assert to_plain("See **June**: [report](http://x/y.pdf)") == "See June: report: http://x/y.pdf"
    long = "\n".join(f"line {i} " + "x" * 100 for i in range(40))
    parts = split_message(long)
    assert all(len(p) <= WA_LIMIT for p in parts) and len(parts) > 1
    print("whatsapp helpers OK | configured:", is_configured(), "| parts:", len(parts))
