"""Phase 4 — email DRAFT tool (draft-only, never sends).

Composes and returns a structured draft. There is deliberately NO SMTP or
email-API send call anywhere in this module. Real sending is deferred to
Phase 7 (behind human approval). The structure is kept simple so flipping
it to "send after approval" later is a small, contained change.
"""


def draft_email(to: str, subject: str, body: str, attachment: str = "") -> dict:
    """Compose an email draft. Returns the draft; sends NOTHING.

    Args:
        to: Recipient address.
        subject: Email subject line.
        body: Email body text.
        attachment: Optional filename/path to reference (e.g. a report PDF).
    """
    draft = {
        "status": "draft",  # never "sent" in Phase 4
        "to": to,
        "subject": subject,
        "body": body,
        "attachment": attachment or None,
    }
    return draft


if __name__ == "__main__":
    d = draft_email(
        "client@example.com",
        "June Sales Report",
        "Hi,\n\nPlease find June's sales summary attached.\n\nBest regards.",
        "june-sales-report.pdf",
    )
    assert d["status"] == "draft"
    print("draft (NOT sent):", d)
