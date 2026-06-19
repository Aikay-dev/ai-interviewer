"""
tone_loader.py — Loads the user's tone.md file into a string for use in the system prompt.

Usage:
    from tone_loader import load_tone
    tone = load_tone("tone.md")
"""


def load_tone(tone_path: str) -> str:
    """
    Read and return the contents of the tone.md file.

    Raises:
        FileNotFoundError: if the file doesn't exist.
        ValueError: if the file is empty.
    """
    try:
        with open(tone_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Tone file not found: {tone_path}\n"
            "Please create a tone.md file describing how you naturally speak."
        )

    if not content:
        raise ValueError(
            f"Tone file is empty: {tone_path}\n"
            "Please add content describing your speaking style."
        )

    return content


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "tone.md"
    try:
        tone = load_tone(path)
        print(f"✅ Tone file loaded ({len(tone)} characters)\n")
        print("--- CONTENT ---")
        print(tone)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        sys.exit(1)
