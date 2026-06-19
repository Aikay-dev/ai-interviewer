"""
cv_parser.py — Extracts text from an uploaded CV PDF using pdfplumber.

Usage:
    from cv_parser import load_cv
    cv_text = load_cv("path/to/cv.pdf")
"""

import pdfplumber


def load_cv(pdf_path: str) -> str:
    """
    Extract and return all text from a PDF CV.

    Raises:
        FileNotFoundError: if the path doesn't exist.
        ValueError: if the PDF appears to be image-based (no extractable text).
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())

            full_text = "\n\n".join(pages_text).strip()

            if not full_text:
                raise ValueError(
                    "CV appears to be a scanned image PDF — no text could be extracted. "
                    "Please use a text-based PDF."
                )

            return full_text

    except FileNotFoundError:
        raise FileNotFoundError(f"CV file not found: {pdf_path}")


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python cv_parser.py <path_to_cv.pdf>")
        sys.exit(1)

    path = sys.argv[1]
    try:
        text = load_cv(path)
        print(f"✅ CV loaded successfully ({len(text)} characters)\n")
        print("--- PREVIEW (first 500 chars) ---")
        print(text[:500])
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        sys.exit(1)
