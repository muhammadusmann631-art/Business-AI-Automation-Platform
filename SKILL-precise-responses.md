---
name: precise-responses-fix
description: "Fix the AI Agent System so the agent gives PRECISE responses — only what the user asked, nothing extra. If user asks for sales amount, give ONLY the amount (no PDF, no graph, no Excel). If user asks for a PDF, give ONLY a PDF. If user asks for a graph, give ONLY a graph. Also improve email to use clean HTML formatting. The agent must understand the EXACT intent and respond with ONLY that."
---

# Precise Responses — Do EXACTLY What Is Asked, Nothing More

## Problem

Right now the agent OVER-DELIVERS. Examples:
- User asks "June ki sales amount btao" → agent gives the amount AND makes a PDF AND makes a graph. WRONG. User sirf amount chahta tha.
- User asks "PDF report banao" → agent makes TWO PDFs. WRONG. Ek hi chahiye.
- User asks "graph dikhao" → agent makes the graph AND a PDF AND an Excel. WRONG. Sirf graph chahiye tha.

The agent must learn: **jo poocha wahi karo. Jo nahi poocha wo mat karo.**

## Root cause

The Planner is creating too many steps. When user says "sales btao", the Planner makes a plan like:
1. Get sales data
2. Make a chart
3. Generate PDF report
4. Draft email

When it should just be:
1. Get sales data
2. Tell the user the number

The fix is in the Planner prompt, Worker prompt, AND Supervisor prompt.

---

## Fix 1 — Planner Prompt (MOST IMPORTANT)

Update the Planner agent's system prompt / instructions. Add this PROMINENTLY at the top:

```
CRITICAL RULE — MATCH THE REQUEST EXACTLY:

You must create a plan that does EXACTLY what the user asked — nothing more, nothing less.

WHAT THE USER ASKS → WHAT THE PLAN SHOULD BE:

- "sales btao" / "amount btao" / "kitni thi" / "dikhao" (asking for DATA)
  → Plan: 1. Query the data  2. Tell the user the answer
  → Do NOT add chart/graph/PDF/Excel/email steps. They did not ask for these.

- "graph banao" / "chart dikhao" (asking for a GRAPH)
  → Plan: 1. Query the data  2. Make ONE chart
  → Do NOT add PDF/Excel/email steps. They did not ask for these.

- "PDF report banao" / "report banao" (asking for a REPORT)
  → Plan: 1. Query the data  2. Generate ONE PDF report
  → Do NOT add chart/Excel/email steps unless explicitly asked.

- "Excel mein do" / "export karo" (asking for EXCEL)
  → Plan: 1. Query the data  2. Export to ONE Excel file
  → Do NOT add chart/PDF/email steps.

- "email bhejo" / "email karo" (asking to SEND EMAIL)
  → Plan: 1. Query the data  2. Draft ONE email  3. Request approval
  → Do NOT add chart/PDF/Excel unless the user specifically said to attach them.

- COMBINED requests like "sales nikal, graph bana, PDF report bana, aur email karo"
  → Plan covers ALL mentioned items — but ONLY the ones mentioned.

RULES:
- Each tool appears AT MOST ONCE in the plan.
- Maximum 2-4 steps per plan.
- If user asks for ONE thing, plan has 1-2 steps (query + that one thing).
- If user asks for MULTIPLE things, plan covers each mentioned item once.
- NEVER assume the user wants a PDF/graph/Excel/email unless they EXPLICITLY say so.
- When in doubt, do LESS not more. The user can always ask for more.
```

## Fix 2 — Worker/Agent Prompt

Update the worker agent's system prompt. Add:

```
RESPONSE RULES:
- Answer ONLY what the user asked. Do not add extras they did not request.
- If they asked "kitni sales thi?" → give the NUMBER. Do not make a chart, PDF, or Excel.
- If they asked "graph banao" → make ONE graph. Do not also make a PDF.
- If they asked "PDF banao" → make ONE PDF. Do not also make a graph.
- Call each tool ONLY ONCE. Never call the same tool twice.
- When giving a number/data answer, keep it concise and clear. Example:
  User: "June ki sales kitni thi?"
  Good: "June ki sales $45,000 thi."
  Bad: "June ki sales $45,000 thi. Maine aapke liye ek PDF report aur graph bhi bana diya hai..." (user ne nahi maanga!)
```

## Fix 3 — Supervisor Prompt

Update the Supervisor prompt. Add:

```
IMPORTANT: Only execute the steps in the plan. Do not add extra tool calls beyond what the Planner specified. If the plan says "1. Query data 2. Tell user" then ONLY query and respond — do not make charts, PDFs, or files the user did not ask for.
```

## Fix 4 — Code-level tool call guard (safety net)

In addition to the prompts, add a code-level check. Before calling any tool, verify it was actually in the plan:

```python
# In the step execution loop
planned_tools = [step.tool_name for step in plan.steps if step.tool_name]

def should_call_tool(tool_name):
    """Only call tools that are in the plan"""
    if tool_name not in planned_tools:
        print(f"[GUARD] blocked unplanned tool call: {tool_name}")
        return False
    return True
```

This prevents the LLM from spontaneously calling tools that weren't in the plan.

---

## Fix 5 — Email HTML Formatting

When the email tool creates a draft, the body should be clean HTML (not plain text). This makes emails look professional when actually sent.

Update the email draft tool to format the body as HTML:

```python
def format_email_body_html(subject: str, body_text: str) -> str:
    """Convert plain text email body to clean HTML"""
    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
            .header {{ background-color: #0f172a; color: #10b981; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .footer {{ background-color: #f1f5f9; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>{subject}</h2>
        </div>
        <div class="content">
            {body_text.replace(chr(10), '<br>')}
        </div>
        <div class="footer">
            Sent via AGI-CORE Business Assistant
        </div>
    </body>
    </html>
    """
```

Update the email sending code to set the MIME type to `text/html` (not `text/plain`) when sending via SMTP:
```python
from email.mime.text import MIMEText
msg = MIMEText(html_body, 'html')  # 'html' not 'plain'
```

Also update the WhatsApp response for emails — WhatsApp cannot render HTML, so for WhatsApp replies send plain text version. Only use HTML for actual email sending.

---

## "Done" checklist

- [ ] **Data query = ONLY data:** "June ki sales btao" → ONLY the number in reply. NO PDF, NO graph, NO Excel generated. Terminal shows NO chart/PDF/Excel tool calls.
- [ ] **Graph = ONLY graph:** "sales ka graph banao" → ONE graph inline. NO PDF, NO Excel generated alongside.
- [ ] **PDF = ONLY PDF:** "PDF report banao" → ONE PDF with download card. NO graph, NO Excel.
- [ ] **Excel = ONLY Excel:** "Excel mein do" → ONE Excel download card. NO PDF, NO graph.
- [ ] **Email = ONLY email draft:** "email bhejo" → ONE draft with approval. NO PDF/graph/Excel unless user explicitly asked.
- [ ] **Combined works:** "sales nikal, graph bana, aur PDF report bana" → all three but each ONCE. Nothing extra.
- [ ] **No duplicate tool calls:** each tool called maximum ONCE per request.
- [ ] **Email body is HTML:** email drafts have clean HTML formatting with header, content, footer.
- [ ] **Email MIME type is text/html** when sent via SMTP.
- [ ] **WhatsApp emails are plain text** (HTML only for actual email, not WhatsApp message).
- [ ] **Unplanned tool calls are blocked** by the code-level guard. Terminal shows [GUARD] if LLM tries.
- [ ] All existing features still work. No regressions.

## How to verify

1. "June ki sales kitni thi?" → just a number. Check terminal — NO [TOOL CALLED] for chart/PDF/Excel.
2. "Sales ka graph banao" → one graph. Check terminal — only make_chart called, NOT generate_report or export_excel.
3. "PDF report banao" → one PDF. No graph.
4. "Graph bana aur PDF bhi bana" → one graph + one PDF. Nothing else.
5. "Email bhejo client@test.com ko sales summary" → one email draft + approval. No files.
6. Check an email draft — body should be HTML with styling.
