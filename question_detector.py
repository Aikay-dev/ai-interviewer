"""
question_detector.py — Lightweight heuristic filter to detect interview questions
from transcribed audio chunks.

Intentionally fast and simple — no LLM involved.
The LLM is only called after a question is confirmed.

Usage:
    from question_detector import is_interview_question

    if is_interview_question(transcript_chunk):
        # send to answer_generator
"""

QUESTION_STARTERS = [
    "tell me",
    "can you",
    "could you",
    "would you",
    "how do",
    "how did",
    "how would",
    "how have",
    "how has",
    "what is",
    "what are",
    "what was",
    "what were",
    "what do",
    "what did",
    "what would",
    "what have",
    "why did",
    "why do",
    "why would",
    "have you",
    "have you ever",
    "describe",
    "walk me through",
    "talk me through",
    "explain",
    "give me an example",
    "give me a sense",
    "share an example",
    "share a time",
    "think about a time",
    "tell us",
    "can you tell",
]

MIN_WORD_COUNT = 5


def is_interview_question(text: str) -> bool:
    """
    Return True if the transcribed chunk looks like an interview question.

    Checks:
    - Minimum word count (filters out filler sounds and short utterances)
    - Ends with a question mark, OR
    - Starts with a known question-starter phrase
    """
    if not text or not text.strip():
        return False

    cleaned = text.strip()
    text_lower = cleaned.lower()
    word_count = len(text_lower.split())

    if word_count < MIN_WORD_COUNT:
        return False

    ends_with_question = cleaned.endswith("?")
    starts_with_question_word = any(text_lower.startswith(s) for s in QUESTION_STARTERS)

    return ends_with_question or starts_with_question_word


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        # Should be detected as questions
        ("Can you walk me through your experience with Python?", True),
        ("Tell me about a time you had to debug something under pressure.", True),
        ("What is your biggest weakness?", True),
        ("How did you approach learning a new technology?", True),
        ("Describe your workflow when starting a new project.", True),
        ("Walk me through your most recent role.", True),
        ("Why did you leave your last job?", True),
        ("Have you ever managed a team?", True),

        # Should NOT be detected as questions
        ("Okay.", False),
        ("Right, so...", False),
        ("Mm-hmm.", False),
        ("Great, thanks for joining us today.", False),
        ("So we're a startup based in Lagos.", False),
        ("Let's get started.", False),
    ]

    passed = 0
    failed = 0

    print("Running question detection tests...\n")
    for text, expected in test_cases:
        result = is_interview_question(text)
        status = "✅" if result == expected else "❌"
        label = "QUESTION" if result else "not a question"
        print(f"{status} [{label}] {text!r}")
        if result == expected:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
