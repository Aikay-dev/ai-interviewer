"""
cli_test.py — Terminal test harness for the core pipeline.

Modes:
    python cli_test.py --cv cv.pdf                          # manual: type questions
    python cli_test.py --cv cv.pdf --live                   # live: mic (default device)
    python cli_test.py --cv cv.pdf --live --device 1        # live: specific mic
    python cli_test.py --cv cv.pdf --live --loopback        # live: system audio
    python cli_test.py --cv cv.pdf --live --loopback --device 16  # live: specific loopback

Run audio_capture.py first to see device indices.
"""

import argparse
import sys
import time
import threading
from datetime import datetime

from cv_parser import load_cv
from tone_loader import load_tone
from answer_generator import build_system_prompt, stream_answer
from question_detector import is_interview_question
from session_exporter import export_session


def parse_args():
    parser = argparse.ArgumentParser(description="AI Interview Assistant — CLI test mode")
    parser.add_argument("--cv", default="cv.pdf", help="Path to CV PDF (default: cv.pdf)")
    parser.add_argument("--tone", default="tone.md", help="Path to tone file (default: tone.md)")
    parser.add_argument("--live", action="store_true", help="Enable live audio transcription mode")
    parser.add_argument("--loopback", action="store_true", help="Use system audio loopback instead of mic")
    parser.add_argument("--device", type=int, default=None, help="Audio device index (run audio_capture.py to list)")
    return parser.parse_args()


def live_mode(system_prompt: str, qa_pairs: list, use_loopback: bool = False, device_index: int = None):
    """
    Live audio mode: listens via mic or system loopback, transcribes speech,
    detects questions, and streams answers automatically.
    """
    from transcriber import Transcriber
    from audio_capture import AudioCapture, list_microphone_devices, list_loopback_devices

    answering_lock = threading.Lock()

    def on_transcript(text: str):
        print(f"\n🎧 Heard: {text}")

        if not is_interview_question(text):
            return

        if not answering_lock.acquire(blocking=False):
            print("   (still answering previous question, skipping)")
            return

        try:
            print(f"\n❓ QUESTION DETECTED: {text}")
            print("\n💬 ANSWER: ", end="", flush=True)
            try:
                full_answer = stream_answer(
                    question=text,
                    system_prompt=system_prompt,
                    on_token=lambda t: print(t, end="", flush=True),
                )
                print("\n")
                qa_pairs.append((text, full_answer))
            except Exception as e:
                print(f"\n❌ API error: {e}\n")
        finally:
            answering_lock.release()

    def on_status(msg: str):
        print(f"ℹ️  {msg}")

    transcriber = Transcriber(on_transcript=on_transcript, on_status=on_status)
    transcriber.load()

    print("⏳ Loading Whisper model (this takes a few seconds)...")
    if not transcriber.wait_until_ready(timeout=60):
        print("❌ Model failed to load.")
        return

    if use_loopback:
        source = "loopback"
        label = "system audio (loopback)"
        if device_index is None:
            devices = list_loopback_devices()
            if not devices:
                print("❌ No loopback device found. Make sure pyaudiowpatch is installed.")
                return
            device_index = devices[0]["index"]
            device_name = devices[0]["name"]
        else:
            device_name = f"device [{device_index}]"
    else:
        source = "microphone"
        label = "microphone"
        if device_index is None:
            devices = list_microphone_devices()
            if not devices:
                print("❌ No microphone device found.")
                return
            device_index = devices[0]["index"]
            device_name = devices[0]["name"]
        else:
            device_name = f"device [{device_index}]"

    print(f"\n🎤 Listening on {label}: {device_name}")
    print("Speak naturally. Questions will be detected and answered automatically.")
    print("Press Ctrl+C to stop.\n")

    capture = AudioCapture(
        device_index=device_index,
        on_audio_chunk=transcriber.feed,
        source=source,
        chunk_seconds=3,
    )

    transcriber.start()
    capture.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        capture.stop()
        transcriber.stop()


def main():
    args = parse_args()

    print("\n🎙  AI Interview Assistant — CLI Test Mode")
    print("=" * 50)

    print(f"\n📄 Loading CV from: {args.cv}")
    try:
        cv_text = load_cv(args.cv)
        print(f"   ✅ CV loaded ({len(cv_text)} characters)")
    except (FileNotFoundError, ValueError) as e:
        print(f"   ❌ {e}")
        sys.exit(1)

    print(f"\n🗣  Loading tone from: {args.tone}")
    try:
        tone_content = load_tone(args.tone)
        print(f"   ✅ Tone loaded ({len(tone_content)} characters)")
    except (FileNotFoundError, ValueError) as e:
        print(f"   ❌ {e}")
        sys.exit(1)

    system_prompt = build_system_prompt(cv_text, tone_content)
    print("\n✅ Session ready. System prompt built.")
    print("=" * 50)

    qa_pairs = []

    if args.live:
        live_mode(system_prompt, qa_pairs, use_loopback=args.loopback, device_index=args.device)
        if qa_pairs:
            save = input(f"\nSave session? ({len(qa_pairs)} Q&A pairs) [y/n]: ").strip().lower()
            if save == "y":
                date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
                path = f"session_{date_str}.txt"
                export_session(qa_pairs, path)
                print(f"✅ Saved to {path}")
        return

    # Manual mode
    print("\nCommands:")
    print("  Type any interview question to get an answer.")
    print("  Type 'detect: <text>' to test question detection.")
    print("  Type 'export' to save the session.")
    print("  Type 'quit' to exit.")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("❓ > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting.")
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            break

        if user_input.lower().startswith("detect:"):
            text_to_test = user_input[7:].strip()
            result = is_interview_question(text_to_test)
            label = "✅ QUESTION" if result else "❌ not a question"
            print(f"   Detection result: {label}\n")
            continue

        if user_input.lower() == "export":
            if not qa_pairs:
                print("   No Q&A pairs to export yet.\n")
                continue
            date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
            txt_path = f"session_{date_str}.txt"
            export_session(qa_pairs, txt_path)
            print(f"   ✅ Session exported to: {txt_path}\n")
            continue

        is_question = is_interview_question(user_input)
        if not is_question:
            print("   ⚠️  This doesn't look like an interview question — answering anyway.\n")

        print("\n💬 ANSWER: ", end="", flush=True)
        try:
            full_answer = stream_answer(
                question=user_input,
                system_prompt=system_prompt,
                on_token=lambda t: print(t, end="", flush=True),
            )
            print("\n")
            qa_pairs.append((user_input, full_answer))
        except EnvironmentError as e:
            print(f"\n❌ {e}\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ API error: {e}\n")


if __name__ == "__main__":
    main()