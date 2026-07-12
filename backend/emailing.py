"""Phase 7 — email tool: draft + REAL send (send only runs after approval).

``draft_email`` composes a draft exactly as in Phase 4 — the agent/tool layer
still only ever produces drafts.

``send_email`` (new in Phase 7) actually delivers via SMTP. It is called
ONLY from the /api/approve handler after an explicit human decision — never
directly by an agent or tool. Credentials come from backend/.env:

    SMTP_HOST=smtp.example.com
    SMTP_PORT=587
    SMTP_USER=bot@example.com
    SMTP_PASSWORD=...
    SMTP_FROM=bot@example.com        (optional; defaults to SMTP_USER)

If credentials are missing, the send is skipped gracefully (with a log) so
the approval flow can be developed and demoed without a real mail server.
"""

import os
import smtplib
from email.message import EmailMessage


def draft_email(to: str, subject: str, body: str, attachment: str = "") -> dict:
    """Compose an email draft. Returns the draft; sends NOTHING.

    Args:
        to: Recipient address.
        subject: Email subject line.
        body: Email body text.
        attachment: Optional filename/path to reference (e.g. a report PDF).
    """
    draft = {
        "status": "draft",  # sending happens only via send_email after approval
        "to": to,
        "subject": subject,
        "body": body,
        "attachment": attachment or None,
    }
    return draft


def send_email(to: str, subject: str, body: str, attachment: str = "") -> str:
    """REALLY send an email via SMTP. Call ONLY from the approval handler.

    Returns a human-readable result string. Missing credentials are not an
    error: the send is skipped with a clear log so dev/demo still works.
    """
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    if not (host and user and password):
        print("[EMAIL] send skipped — no SMTP credentials configured. "
              "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in backend/.env")
        return f"Email approved but not sent — SMTP not configured (recipient: {to})."

    port = int(os.getenv("SMTP_PORT", "587"))
    # Support either SMTP_FROM or EMAIL_FROM; fall back to the login user.
    # Ignore an unfilled placeholder / non-address (Gmail rejects a From that
    # is not the authenticated user anyway).
    sender = os.getenv("SMTP_FROM") or os.getenv("EMAIL_FROM") or user
    if not sender or "@" not in sender or "your-email@" in sender:
        sender = user

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    text = body
    if attachment:
        # Phase 7 keeps it light: reference the report link/path in the body
        # rather than MIME-attaching files.
        text += f"\n\nAttachment: {attachment}"
    msg.set_content(text)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)

    print(f"[EMAIL] sent to {to} — subject: {subject}")
    return f"Email sent to {to} — subject: {subject}."


if __name__ == "__main__":
    d = draft_email(
        "client@example.com",
        "June Sales Report",
        "Hi,\n\nPlease find June's sales summary attached.\n\nBest regards.",
        "june-sales-report.pdf",
    )
    assert d["status"] == "draft"
    print("draft (NOT sent):", d)

    # Without credentials this must skip gracefully, not crash.
    print(send_email("client@example.com", "Test", "Body"))
