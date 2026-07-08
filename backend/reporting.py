"""Phase 4 — real PDF report generation (fpdf2).

Produces a genuine .pdf file on disk under backend/reports/ and returns its
path + filename. Kept separate from the agent code.
"""

import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

REPORTS_DIR = Path(__file__).parent / "reports"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "report"


def generate_report(title: str, body: str) -> dict:
    """Write a real PDF report and return {path, filename}.

    Args:
        title: Heading shown at the top of the report.
        body: The report content (plain text; newlines become new lines).
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{_slug(title)}-{timestamp}.pdf"
    path = REPORTS_DIR / filename

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, title)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Generated {datetime.now():%Y-%m-%d %H:%M}")
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 12)
    # Latin-1 is fpdf's core-font encoding; drop anything outside it safely.
    safe_body = body.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 8, safe_body)

    pdf.output(str(path))
    return {"path": str(path), "filename": filename}


if __name__ == "__main__":
    result = generate_report(
        "June Sales Report",
        "Sales for June were 45000.\n\nThis is a standalone test of the "
        "PDF report generator.",
    )
    print("generated:", result)
