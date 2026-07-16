---
name: batch-3-bulk-operations-and-voice-input
description: "Add two final features: (1) Bulk Operations — user gives one command and the system performs the action for multiple items at once (e.g. 'saare overdue clients ko reminder bhejo' → finds all overdue, drafts personalized emails for each, shows them for ONE approval, sends all). (2) Voice Input — mic button in chat, user speaks instead of typing, Web Speech API converts to text, system processes normally. These are the final power features."
---

# Batch 3 — Bulk Operations + Voice Input (FINAL)

## Build order: Bulk Operations FIRST, then Voice Input.

Bulk is more complex (backend + frontend). Voice is frontend-only.

---

## Feature 1 — Bulk Operations

### What it does

User gives ONE command that affects MULTIPLE items. Instead of doing each one manually, the system handles all of them in one go.

### Examples:

**Example 1 — Bulk reminder emails:**
User: *"Saare overdue clients ko reminder email bhejo"*
→ System finds all overdue invoices (e.g. 5)
→ Drafts a personalized email for EACH client (different to/amount/invoice number)
→ Shows ALL drafts in ONE approval card: "5 emails ready to send. Review and approve?"
→ User clicks Approve → all 5 emails sent
→ Or user clicks Reject → none sent

**Example 2 — Bulk status update:**
User: *"Saare pending invoices jo December se pehle ki hain, unko overdue mark karo"*
→ System finds matching invoices
→ Shows: "8 invoices will be marked as overdue. Approve?"
→ Approve → all updated

**Example 3 — Bulk export:**
User: *"Saare active customers ka data Excel mein do"*
→ System queries all active customers
→ Exports to ONE Excel file
→ Download card appears

### Backend — what to build:

**1. Bulk operation handler (`backend/bulk.py`):**

```python
class BulkOperation:
    """Represents a bulk action on multiple items"""
    operation_id: str
    action: str  # "send_email", "update_status", "export"
    items: list  # the individual items to act on
    total_count: int
    preview: list  # first 3-5 items shown to user
    status: str  # "pending_approval", "approved", "rejected", "completed"

def prepare_bulk_emails(query_result: list, template: str) -> BulkOperation:
    """
    Takes a list of items (e.g. overdue invoices with customer info)
    Generates a personalized email draft for each
    Returns a BulkOperation ready for approval
    """
    emails = []
    for item in query_result:
        email = {
            "to": item["customer_email"],
            "subject": f"Payment Reminder — Invoice {item['invoice_number']}",
            "body": generate_personalized_body(item, template)
        }
        emails.append(email)
    
    return BulkOperation(
        operation_id=generate_id(),
        action="send_email",
        items=emails,
        total_count=len(emails),
        preview=emails[:3],  # show first 3 for review
        status="pending_approval"
    )

def execute_bulk(operation: BulkOperation) -> dict:
    """Execute all items in the bulk operation"""
    success = 0
    failed = 0
    for item in operation.items:
        try:
            # execute individual action (send email, update row, etc.)
            success += 1
        except Exception as e:
            failed += 1
    
    return {"success": success, "failed": failed, "total": operation.total_count}
```

**2. Bulk approval flow:**

The existing approval system (Phase 7) handles single actions. Extend it for bulk:

- When a bulk operation is created, return it as `pending_bulk_approval` in the response:
```json
{
    "reply": "5 overdue clients found. Personalized reminder emails ready.",
    "pending_bulk_approval": {
        "bulk_id": "bulk-abc-123",
        "action": "send_email",
        "total_count": 5,
        "preview": [
            {"to": "ahmed@corp.com", "subject": "Payment Reminder — INV-001", "body": "..."},
            {"to": "sara@llc.com", "subject": "Payment Reminder — INV-005", "body": "..."},
            {"to": "tech@solutions.com", "subject": "Payment Reminder — INV-008", "body": "..."}
        ],
        "remaining": 2,
        "risk_reason": "Sending 5 emails to external recipients"
    }
}
```

- `POST /api/bulk/approve` — approves and executes ALL items.
- `POST /api/bulk/reject` — cancels ALL items.

**3. Personalized email templates:**

When drafting bulk emails, each email should be personalized:
- Customer name in greeting.
- Specific invoice number and amount.
- Due date.
- Professional HTML formatting (using the HTML email template from earlier).

Template example:
```
Dear {customer_name},

This is a friendly reminder that Invoice {invoice_number} 
for ${amount} was due on {due_date} and is currently outstanding.

We would appreciate payment at your earliest convenience.

Best regards,
AGI-CORE Business Team
```

**4. Bulk operation types to support:**

| User says | Action |
|---|---|
| "overdue clients ko reminder bhejo" | Find overdue → draft personalized emails → bulk approve → send |
| "saare pending invoices overdue mark karo" | Find old pending → bulk status update → approve → update |
| "active customers ka Excel do" | Find active → export all to Excel (no approval needed — read-only) |
| "saare products ka price 10% badhao" | Find products → calculate new prices → approve → update |

**5. Update agent prompts:**

Planner prompt add:
```
BULK OPERATIONS:
- When user says "saare", "all", "sab", "bulk", or refers to multiple items → this is a BULK operation.
- Plan: 1. Query all matching items  2. Prepare bulk action  3. Show preview for approval
- Bulk operations ALWAYS need approval (even read-only exports show a count confirmation first).
```

Worker prompt add:
```
- For bulk operations, use the bulk tools. Show a preview of what will happen and ask for approval.
- Always show the total count: "5 emails will be sent" / "8 invoices will be updated".
```

### Frontend — Bulk approval card:

When `pending_bulk_approval` is in the response, show a special bulk approval card:

```
┌──────────────────────────────────────────────────────────────┐
│ 📦 BULK ACTION — 5 Reminder Emails                          │
│                                                              │
│ Preview (showing 3 of 5):                                    │
│                                                              │
│ ┌─ Email 1 ──────────────────────────────────────────────┐  │
│ │ To: ahmed@corp.com                                      │  │
│ │ Subject: Payment Reminder — INV-001                     │  │
│ │ Amount: $12,000 (overdue since Dec 15)                  │  │
│ └─────────────────────────────────────────────────────────┘  │
│                                                              │
│ ┌─ Email 2 ──────────────────────────────────────────────┐  │
│ │ To: sara@llc.com                                        │  │
│ │ Subject: Payment Reminder — INV-005                     │  │
│ │ Amount: $8,500 (overdue since Jan 3)                    │  │
│ └─────────────────────────────────────────────────────────┘  │
│                                                              │
│ ┌─ Email 3 ──────────────────────────────────────────────┐  │
│ │ To: tech@solutions.com                                  │  │
│ │ Subject: Payment Reminder — INV-008                     │  │
│ │ Amount: $3,200 (overdue since Jan 20)                   │  │
│ └─────────────────────────────────────────────────────────┘  │
│                                                              │
│ + 2 more emails                                              │
│                                                              │
│     [✓ Approve All (5)]          [✕ Reject All]             │
└──────────────────────────────────────────────────────────────┘
```

- Dark AGI-CORE theme.
- Shows preview of first 3 items, "+ N more" for the rest.
- "Approve All" (green) and "Reject All" (red) buttons.
- After approve: "✅ 5 emails sent successfully" (or "4 sent, 1 failed").
- Buttons lock after click (no double-fire).

### Logging:
- `[BULK] prepared: 5 reminder emails for overdue invoices`.
- `[BULK] approved: bulk-abc-123 — executing 5 items`.
- `[BULK] completed: 5/5 success, 0 failed`.
- `[BULK] rejected: bulk-abc-123 — cancelled`.

---

## Feature 2 — Voice Input

### What it does

A microphone button in the chat input area. User clicks it → speaks → their voice is converted to text → sent as a normal chat message. System processes it exactly like typed text.

### How it works (browser Web Speech API — FREE, no external service):

```javascript
// Web Speech API — built into modern browsers, no API key needed
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();

recognition.lang = 'en-US';  // or 'ur-PK' for Urdu
recognition.continuous = false;  // stop after one sentence
recognition.interimResults = true;  // show text as user speaks

recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    // Put the transcript into the chat input field
    setMessage(transcript);
};

recognition.onerror = (event) => {
    console.error('Speech error:', event.error);
    // Show friendly error to user
};
```

### Frontend — what to build:

**1. Mic button:**
- Place a 🎙️ microphone icon button RIGHT NEXT to the text input (left of Send button or right of input).
- Same size as Send button, AGI-CORE themed.
- Default state: mic icon (gray/white).
- Recording state: mic icon PULSING RED + "Listening..." text animation.
- After speech: transcript appears in the input field, user can edit before sending.

**2. States:**

| State | Visual | Behavior |
|---|---|---|
| Idle | 🎙️ (normal) | Click to start listening |
| Listening | 🔴 (pulsing) + "Listening..." | Speaking → text appears in input live |
| Processing | text in input field | User reviews, edits if needed, then clicks Send |
| Error | brief error message | "Microphone not available" or "Could not understand" |

**3. Behavior rules:**
- Click mic → start listening. Click again → stop listening.
- After speech ends (user stops talking), auto-stop listening after 2-3 seconds of silence.
- Interim results show in the input field in real-time AS the user speaks (shows partial text).
- Final result replaces interim text in the input field.
- User can EDIT the text before clicking Send (speech-to-text isn't perfect).
- Clicking Send works exactly like typing — no special handling needed.
- If the browser doesn't support Web Speech API → hide the mic button entirely (don't crash).

**4. Language support:**
- Default language: English ('en-US').
- Also support Urdu ('ur-PK') if available.
- Optionally: auto-detect or let user pick in settings.
- Roman Urdu (like "June ki sales btao") works best with English language setting since it's transliterated English characters.

**5. Permissions:**
- Browser will ask for microphone permission on first click.
- If denied → show a friendly message: "Microphone access denied. Please allow microphone in browser settings."

### Important:
- This is 100% frontend — NO backend changes needed. The speech is converted to text in the browser, then sent as a normal message.
- Web Speech API is FREE — no external service, no API key, no cost.
- Works in Chrome, Edge, Safari. Firefox has limited support — that's okay.
- NO audio is sent to your server — privacy safe. Google's speech service processes it (built into Chrome).

---

## "Done" checklist

### Bulk Operations:
- [ ] **"Overdue clients ko reminder bhejo"** → system finds all overdue → shows bulk approval card with email previews → Approve All → all sent.
- [ ] **Bulk approval card shows** preview (first 3) + "+ N more" + Approve All / Reject All buttons.
- [ ] **Approve All** executes all items. Result shows success/fail count.
- [ ] **Reject All** cancels everything. Nothing executed.
- [ ] **Personalized emails:** each email has correct customer name, invoice number, amount.
- [ ] **Bulk status update works:** "pending invoices overdue mark karo" → finds → approve → updated.
- [ ] **Bulk export works:** "active customers Excel mein do" → one Excel file with all.
- [ ] **[BULK] logs** appear in terminal.
- [ ] **Buttons lock** after click — no double-fire.
- [ ] **Bulk operations appear in traces** (Phase 9).

### Voice Input:
- [ ] **Mic button visible** next to the chat input — 🎙️ icon, AGI-CORE themed.
- [ ] **Click mic → listening state** — button pulses red, "Listening..." appears.
- [ ] **Speak → text appears** in the input field in real-time.
- [ ] **Speech ends → auto-stop** after silence. Text stays in input for review.
- [ ] **Click Send → normal processing** — exactly like typed text.
- [ ] **User can edit** the transcript before sending.
- [ ] **Mic not supported → button hidden** (no crash).
- [ ] **Permission denied → friendly message** shown.
- [ ] **No backend changes** — purely frontend.

### Overall:
- [ ] All previous features still work (P&L, alerts, import, charts, auth, WhatsApp, etc.).
- [ ] AGI-CORE dark theme consistent.
- [ ] No regressions.

---

## How to verify

1. **Bulk email:** "overdue clients ko reminder bhejo" → bulk card shows → approve → emails sent → success count.
2. **Bulk reject:** trigger another bulk → reject → nothing sent.
3. **Bulk update:** "pending invoices overdue mark karo" → approve → check /admin → statuses changed.
4. **Voice:** click mic → say "June ki sales btao" → text appears → send → correct answer.
5. **Voice edit:** click mic → speak → edit the text → send → works.
6. **No mic browser:** open in a browser without speech API → mic button not shown.
