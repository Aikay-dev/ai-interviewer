"""
session_exporter.py — Saves the Q&A session to a .txt or .pdf file.

Usage:
    from session_exporter import export_session

    qa_pairs = [
        ("Can you walk me through your background?", "Sure, I've been a backend engineer..."),
        ("What's your biggest strength?", "Honestly, it's debugging under pressure..."),
    ]
    export_session(qa_pairs, output_path="session_2026-06-17.txt")
    export_session(qa_pairs, output_path="session_2026-06-17.pdf")
"""

import os
from datetime import datetime
from typing import List, Tuple


def _format_session_text(qa_pairs: List[Tuple[str, str]], date_str: str) -> str:
    """Format the Q&A pairs as plain text."""
    lines = [f"INTERVIEW SESSION — {date_str}", ""]
    for i, (question, answer) in enumerate(qa_pairs, start=1):
        lines.append(f"Q{i}: {question}")
        lines.append(f"A{i}: {answer}")
        lines.append("")
    return "\n".join(lines).strip()


def export_as_txt(qa_pairs: List[Tuple[str, str]], output_path: str) -> None:
    """Save the session as a plain .txt file."""
    date_str = datetime.now().strftime("%d %B %Y")
    content = _format_session_text(qa_pairs, date_str)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def export_as_pdf(qa_pairs: List[Tuple[str, str]], output_path: str) -> None:
    """Save the session as a PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib import colors
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install it with: pip install reportlab"
        )

    date_str = datetime.now().strftime("%d %B %Y")
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#1a1a1a"),
        spaceAfter=12,
    )
    question_style = ParagraphStyle(
        "Question",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#0066cc"),
        fontName="Helvetica-Bold",
        spaceBefore=16,
        spaceAfter=4,
    )
    answer_style = ParagraphStyle(
        "Answer",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#1a1a1a"),
        leading=16,
        spaceAfter=8,
    )

    story = [
        Paragraph(f"Interview Session — {date_str}", title_style),
        Spacer(1, 0.3 * cm),
    ]

    for i, (question, answer) in enumerate(qa_pairs, start=1):
        story.append(Paragraph(f"Q{i}: {question}", question_style))
        story.append(Paragraph(f"A{i}: {answer}", answer_style))

    doc.build(story)


def export_session(
    qa_pairs: List[Tuple[str, str]],
    output_path: str,
) -> None:
    """
    Export the Q&A session to a file.
    Format is inferred from the file extension (.txt or .pdf).

    Args:
        qa_pairs:    List of (question, answer) tuples in order.
        output_path: Full path including filename and extension.
    """
    if not qa_pairs:
        raise ValueError("No Q&A pairs to export.")

    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".pdf":
        export_as_pdf(qa_pairs, output_path)
    elif ext == ".txt":
        export_as_txt(qa_pairs, output_path)
    else:
        raise ValueError(f"Unsupported export format: {ext!r}. Use .txt or .pdf")


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_qa = [
        (
            "Can you walk me through a time you debugged a production issue under pressure?",
            "Yeah, one that comes to mind was at Biddy — we had a payments issue that was "
            "silently dropping transactions for about 40 minutes before monitoring caught it. "
            "I pulled the CloudWatch logs, traced it back to a race condition in the order "
            "completion handler, fixed it with a database lock and deployed within the hour. "
            "After that I added alerts for that specific pattern so we'd catch it faster next time.",
        ),
        (
            "How do you approach learning a new technology?",
            "Honestly I start by building something real with it — not just following a tutorial. "
            "I pick a small project that's close to what I'd actually use the tech for, and I let "
            "the friction teach me. Documentation is secondary; I read it when I'm stuck.",
        ),
    ]

    txt_path = "/tmp/test_session.txt"
    pdf_path = "/tmp/test_session.pdf"

    export_session(sample_qa, txt_path)
    print(f"✅ TXT exported: {txt_path}")

    try:
        export_session(sample_qa, pdf_path)
        print(f"✅ PDF exported: {pdf_path}")
    except ImportError as e:
        print(f"⚠️  PDF skipped: {e}")

    print("\n--- TXT PREVIEW ---")
    with open(txt_path) as f:
        print(f.read())
