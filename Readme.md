# AI Interview Assistant

A Windows desktop app that listens to your interview in real time, transcribes what the interviewer says, predicts the intended question, and generates a natural spoken answer on screen — personalised to your CV, tone, and the job you're applying for.

The window is invisible to screen capture, so it won't show up on Google Meet, Zoom, or Teams screen shares.

---

## How it works

1. Open the app before your interview
2. Click 📄 to load your CV (PDF), tone guide, and paste the job description
3. Click 🎤 to select your microphone
4. Click ▶ to start listening
5. The app captures your mic — which picks up the interviewer's voice from your phone speaker
6. Whisper transcribes audio live, showing words as they come in
7. Gemini Flash reads the full conversation transcript, finds the last unanswered question, and generates an answer in your voice — even through noisy or garbled transcription
8. Each answer appears as its own segment — navigate between them with the ▲▼ buttons
9. New answers append at the bottom without disturbing what you're currently reading
10. Click Export to save the full session when you're done

---

## Setup

### Requirements

- Windows 10 version 2004+ or Windows 11
- Python 3.11+
- NVIDIA GPU recommended (GTX 1650 or better) for fast transcription
- An [OpenRouter](https://openrouter.ai/keys) API key

### Install dependencies

```bash
pip install -r requirements.txt
```

For GPU transcription (recommended):

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

### Configure environment

Copy `.env.example` to `.env` and fill in your details:

```
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-3.1-flash-lite:nitro
WHISPER_MODEL=small
```

### Run

```bash
python main.py
```

---

## The interface

**Top bar** — status dot, mic picker (🎤), files (📄), settings (⚙), export, start/stop

**Live transcript bar** — shows what Whisper is hearing in real time as the interviewer speaks

**Detected question** — the clean predicted version of what was asked, with a Copy button

**Answer area** — large bold text, one answer per segment. Navigate with ▲▼ buttons on the right:
- The ▼ button turns blue when a newer answer has arrived
- Current segment never moves while you're reading

**Override input** — always focused, always ready. Type or paste a corrected question and press Enter to regenerate the answer instantly. Copy the detected question first if you just need to tweak it.

---

## Project structure

```
interview-assistant/
├── main.py                  # App entry point + screen capture exclusion
├── audio_capture.py         # Mic capture via sounddevice
├── transcriber.py           # Whisper transcription + Gemini answer loop
├── question_detector.py     # Lightweight pre-filter
├── answer_generator.py      # OpenRouter streaming (CLI mode)
├── cv_parser.py             # PDF CV text extraction
├── tone_loader.py           # Loads tone.md
├── session_exporter.py      # Export Q&A to .txt or .pdf
├── cli_test.py              # Terminal test harness (no GUI)
├── tone.md                  # Your speaking style — edit this
├── cv.pdf                   # Drop your CV here
├── requirements.txt
├── .env.example
└── ui/
    ├── main_window.py       # Main PyQt6 window
    ├── answer_panel.py      # Segmented answer display + navigation
    └── settings_panel.py    # Settings panel (legacy)
```

---

## The tone.md file

Edit this before your interview to teach the app your voice:

```markdown
# My Interview Tone Guide

## How I naturally speak
- I talk conversationally but stay professional
- I don't over-explain. I make my point and stop.
- I use phrases like "So what I did was...", "The honest answer is...", "What I've found is..."
- I give short examples rather than long stories

## Things I want to avoid
- Hedging or qualifying my experience
- Corporate buzzwords
- Sounding rehearsed

## My confidence level
- I NEVER open by saying what I haven't done. I lead with what I did.
- I own my experience without being arrogant

## How to handle experience questions
- If asked if I have done X and my CV shows anything related — the answer is YES, then explain
- "Managing" includes coordinating, leading delivery, making decisions, mentoring, reviewing work, owning outcomes
```

---

## The job description field

Click 📄 and paste the full job description into the text area at the bottom. The AI uses it to:
- Frame answers around skills the role specifically requires
- Reference technologies and tools the company uses
- Match the seniority and focus of the position

---

## Screen capture invisibility

The app uses `SetWindowDisplayAffinity` (Windows API) to exclude itself from all screen capture:
- Fully visible on your own screen
- Shows as a black rectangle in Google Meet, Zoom, Teams, OBS, or any screen recorder
- Works on Windows 10 (2004+) and Windows 11

---

## Tips for best results

- **Use a quiet room** — background noise causes Whisper to hallucinate random words
- **Phone on speaker** — place it near your mic so the interviewer's voice is captured clearly
- **Use the override box** — if the question is wrong, copy it, tweak it, hit Enter
- **GPU is important** — Whisper on a GTX 1650 transcribes in ~200ms; CPU adds 2–3 seconds per chunk
- **The AI handles noise** — repeated words, garbled phrases, filler words are all filtered out automatically

---

## Models

| Component | Default | Purpose |
|-----------|---------|---------|
| Transcription | Whisper `small` (local, GPU) | Real-time speech to text |
| Answer generation | `google/gemini-3.1-flash-lite:nitro` | Question prediction + answer generation |

Swap the answer model in `.env` — any OpenRouter model works. Claude Sonnet gives better quality; Gemini Flash is faster and cheaper.

---

## Building a standalone .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed main.py
```

Output in `dist/main.exe`. The Whisper model (~500MB for `small`) downloads on first run.