"""
answer_generator.py — Builds the session system prompt and streams AI answers
via OpenRouter (OpenAI-compatible endpoint).

Usage:
    from answer_generator import build_system_prompt, stream_answer

    system_prompt = build_system_prompt(cv_text, tone_content)
    stream_answer("Tell me about yourself.", system_prompt, on_token=print)
"""

import os
from typing import Callable

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def build_system_prompt(cv_text: str, tone_content: str) -> str:
    """
    Construct the full system prompt for the session.
    Called once when the user clicks Start Listening.
    Reused for every question in the session.
    """
    return f"""You are an AI interview answer assistant. You are helping a candidate answer interview questions live, in real time.

[CANDIDATE PROFILE — from their CV]
{cv_text}

[TONE GUIDE — how this candidate speaks]
{tone_content}

[YOUR JOB]
When you receive an interview question, generate a natural spoken answer that:
- Sounds exactly like the candidate would say it out loud — not like an essay
- Uses their tone guide above, not generic interview language
- References their real experience from their CV where relevant
- Is concise: 3–6 sentences unless the question genuinely needs more
- Does NOT start with "Great question!" or any filler opener
- Does NOT use bullet points or markdown formatting — write it as flowing speech
- Ends cleanly — no trailing phrases like "I hope that answers your question
- Never open by negating your experience ("I didn't formally manage..." / "I haven't done X exactly but..."). Lead with what you DID do. Own it directly.
- If the candidate's CV shows relevant experience, frame it as direct experience — don't qualify it away.
- I never open an answer by saying what I haven't done. I lead with what I did."

Output ONLY the answer. Nothing else."""


def get_client() -> OpenAI:
    """Create and return an OpenAI client pointed at OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. "
            "Add it to your .env file: OPENROUTER_API_KEY=your_key_here"
        )
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def stream_answer(
    question: str,
    system_prompt: str,
    on_token: Callable[[str], None],
) -> str:
    """
    Stream an AI-generated answer for the given question.

    Args:
        question:      The detected interview question.
        system_prompt: The session system prompt (CV + tone).
        on_token:      Callback called with each token as it arrives.
                       In CLI mode: pass `print`.
                       In GUI mode: connect to a PyQt signal.

    Returns:
        The full answer text (assembled from all tokens).
    """
    client = get_client()
    model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5")

    stream = client.chat.completions.create(
        model=model,
        max_tokens=400,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        extra_headers={
            "HTTP-Referer": "https://interview-assistant.local",
            "X-Title": "AI Interview Assistant",
        },
    )

    full_answer = []
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            on_token(token)
            full_answer.append(token)

    return "".join(full_answer)


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Minimal smoke test — uses placeholder CV and tone if real files aren't provided
    dummy_cv = (
        "Software Engineer with 5 years experience. "
        "Worked at Biddy as a backend engineer. "
        "Skilled in Python, AWS, and distributed systems."
    )
    dummy_tone = (
        "I speak conversationally but stay professional. "
        "I'm direct and don't over-explain. "
        "I give short, concrete examples."
    )

    system_prompt = build_system_prompt(dummy_cv, dummy_tone)

    question = sys.argv[1] if len(sys.argv) > 1 else "Tell me about yourself."

    print(f"\n🎤 QUESTION: {question}\n")
    print("💬 ANSWER: ", end="", flush=True)

    try:
        full = stream_answer(question, system_prompt, on_token=lambda t: print(t, end="", flush=True))
        print(f"\n\n✅ Done ({len(full)} chars)")
    except EnvironmentError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ API error: {e}")
        sys.exit(1)
