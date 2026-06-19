"""
transcriber.py -- Live interview transcription with growing context prompt.

Architecture:
- Whisper transcribes audio every 0.5s, appending to a growing transcript
- Every 2s, the full transcript is sent to Claude
- Claude decides: answer the last question, or reply WAITING if not ready
- Answered questions are marked in the transcript so Claude has full context
"""

import threading
import queue
import numpy as np
import os
import time
from typing import Callable, Optional
from dotenv import load_dotenv
load_dotenv()

SAMPLE_RATE    = 16000
BUFFER_SECONDS = 6
CHECK_INTERVAL = 2.0   # how often we send transcript to Claude for a decision

SYSTEM_PROMPT = """You are an AI assistant helping a job interview candidate in real time.

You will receive a raw transcript of a live interview. The transcript contains everything the microphone picks up -- the interviewer asking questions, the candidate speaking their answers, background noise, repeated words, and speech recognition errors. All of this is mixed together in one stream.

Your job:
1. Scan the full transcript for interviewer questions
2. Find the LAST interviewer question that does NOT yet have a meaningful candidate response after it
3. Answer that question in the candidate's voice
4. If all questions in the transcript already have responses after them -- reply WAITING (waiting for the next interviewer question)

How to tell questions from responses:
- Interviewer questions: "tell me about...", "have you ever...", "what is your...", "how do you...", "can you walk me through...", "describe a time..."
- Candidate responses: "well I have...", "so what I did was...", "at my last job...", "yeah...", "the honest answer is...", "what I've found is..."

Important:
- If the candidate is currently speaking their answer -- that is fine, keep looking for unanswered questions before their response
- Never say WAITING just because the candidate is talking -- they are buying time while you generate the answer
- Only say WAITING if there is genuinely no unanswered interviewer question in the entire transcript

The transcript is noisy -- read through errors and repetition to understand intent.

Format your response as:
QUESTION: <the clean version of the interviewer's question>
ANSWER: <your answer in the candidate's voice>

Or if no unanswered question exists yet:
WAITING"""

def _clean_transcript(text: str) -> str:
    """
    Remove repeated words/phrases that Whisper produces when it re-transcribes
    the same audio. E.g. "what is what is your name your name" → "what is your name"
    Also strips filler like "Thank you." at the start.
    """
    if not text:
        return text

    # Remove common Whisper filler artifacts at the start
    for filler in ["Thank you.", "Thanks.", "Mm-hmm.", "Mm.", "Hmm.", "Uh,", "Um,"]:
        if text.startswith(filler):
            text = text[len(filler):].strip()

    # Collapse repeated consecutive word sequences (case + punctuation insensitive)
    # "what is what is your name your name" → "what is your name"
    import re
    words = text.split()
    cleaned = []
    i = 0

    def norm(w):
        return re.sub(r"[^a-z0-9]", "", w.lower())

    while i < len(words):
        found_repeat = False
        for n in range(min(6, len(words) - i), 1, -1):
            chunk      = [norm(w) for w in words[i:i+n]]
            next_chunk = [norm(w) for w in words[i+n:i+2*n]]
            if chunk == next_chunk and len(next_chunk) == n:
                cleaned.extend(words[i:i+n])
                i += 2 * n
                found_repeat = True
                break
        if not found_repeat:
            cleaned.append(words[i])
            i += 1

    return " ".join(cleaned).strip()


def _extract_new_tail(prev: str, curr: str) -> str:
    """
    Given the previous Whisper output and the current one,
    return only the new words that appeared at the end.

    Whisper rewrites its entire output each tick (rolling buffer),
    so we find the longest common prefix and return what's new after it.
    """
    if not prev:
        return curr.strip()

    prev_words = prev.strip().split()
    curr_words = curr.strip().split()

    # Find how many words from the start are shared
    shared = 0
    for i, (p, c) in enumerate(zip(prev_words, curr_words)):
        if p.lower().rstrip(".,?!") == c.lower().rstrip(".,?!"):
            shared = i + 1
        else:
            break

    new_words = curr_words[shared:]
    return " ".join(new_words).strip()


class Transcriber:

    def __init__(
        self,
        on_answer: Callable[[str, str], None],   # (question, answer)
        cv_text: str,
        tone_content: str,
        job_text: str = "",
        on_partial: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        model_size: Optional[str] = None,
    ):
        self.on_answer     = on_answer
        self.cv_text       = cv_text
        self.tone_content  = tone_content
        self.job_text      = job_text
        self.on_partial    = on_partial or (lambda s: None)
        self.on_status     = on_status  or (lambda s: None)
        self.model_size    = model_size or os.getenv("WHISPER_MODEL", "small")

        self._model        = None
        self._model_ready  = threading.Event()
        self._audio_queue  = queue.Queue()
        self._stop_event   = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._load_thread:   Optional[threading.Thread] = None

        # The growing interview transcript
        self._transcript      = ""
        self._transcript_lock = threading.Lock()
        self._noise_floor     = 0.008  # default, overwritten after calibration
        self._speech_threshold = 0.016  # default, overwritten after calibration
        self._calibrated      = False

    # ── Public API ────────────────────────────────────────────────────────────

    def load(self):
        self._load_thread = threading.Thread(target=self._load_model, daemon=True)
        self._load_thread.start()

    def wait_until_ready(self, timeout: float = 60.0) -> bool:
        return self._model_ready.wait(timeout=timeout)

    def is_ready(self) -> bool:
        return self._model_ready.is_set()

    def start(self):
        if not self.is_ready():
            raise RuntimeError("Model not loaded yet.")
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def feed(self, audio_chunk: np.ndarray):
        if self.is_ready() and not self._stop_event.is_set():
            self._audio_queue.put(audio_chunk)

    def stop(self):
        self._stop_event.set()
        self._audio_queue.put(None)
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

    def get_transcript(self) -> str:
        with self._transcript_lock:
            return self._transcript

    # ── Model loading ─────────────────────────────────────────────────────────

    def calibrate(self, duration: float = 3.0):
        """
        Measure ambient noise for `duration` seconds, then ask user to speak
        for another `duration` seconds to measure speech level.
        Sets dynamic RMS thresholds.
        """
        import sounddevice as sd

        self.on_status("🎙 Calibrating -- stay quiet…")
        noise_samples = []

        def noise_cb(indata, frames, t, status):
            noise_samples.append(float(np.sqrt(np.mean(indata ** 2))))

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                            callback=noise_cb, blocksize=4096):
            time.sleep(duration)

        noise_floor = float(np.mean(noise_samples)) if noise_samples else 0.005
        self.on_status(f"🎙 Now speak normally for {duration:.0f}s…")

        speech_samples = []

        def speech_cb(indata, frames, t, status):
            speech_samples.append(float(np.sqrt(np.mean(indata ** 2))))

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                            callback=speech_cb, blocksize=4096):
            time.sleep(duration)

        speech_level = float(np.mean(speech_samples)) if speech_samples else noise_floor * 4

        # Threshold sits halfway between noise floor and speech level
        self._noise_floor      = noise_floor
        self._speech_threshold = noise_floor + (speech_level - noise_floor) * 0.4
        self._calibrated       = True

        self.on_status(
            f"✅ Calibrated -- noise: {noise_floor:.4f}, "
            f"speech: {speech_level:.4f}, "
            f"threshold: {self._speech_threshold:.4f}"
        )

    def _load_model(self):
        try:
            self.on_status(f"Loading Whisper '{self.model_size}'…")
            import sys
            for p in sys.path:
                if 'local-packages' in p or 'site-packages' in p:
                    for lib in ['cublas', 'cudnn', 'cuda_runtime', 'nvjitlink', 'curand']:
                        dll_path = os.path.join(p, 'nvidia', lib, 'bin')
                        if os.path.isdir(dll_path):
                            os.add_dll_directory(dll_path)

            from faster_whisper import WhisperModel
            try:
                self._model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
                self.on_status(f"Whisper '{self.model_size}' loaded on GPU ✅")
            except Exception as e:
                self.on_status(f"GPU unavailable, using CPU…")
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                self.on_status(f"Whisper '{self.model_size}' loaded on CPU ✅")
            self._model_ready.set()
        except Exception as e:
            self.on_status(f"❌ Failed to load Whisper: {e}")

    # ── Worker ────────────────────────────────────────────────────────────────

    def _worker(self):
        buffer_size  = BUFFER_SECONDS * SAMPLE_RATE
        audio_buffer = np.zeros(buffer_size, dtype=np.float32)
        pending      = []
        last_whisper_text = ""
        next_check_at = time.time() + CHECK_INTERVAL
        answering = threading.Lock()

        while not self._stop_event.is_set():
            # Drain audio queue
            try:
                while True:
                    chunk = self._audio_queue.get_nowait()
                    if chunk is None:
                        return
                    pending.append(chunk)
            except queue.Empty:
                pass

            now = time.time()

            if pending:
                new_audio = np.concatenate(pending)
                pending.clear()
                if len(new_audio) >= buffer_size:
                    audio_buffer = new_audio[-buffer_size:]
                else:
                    audio_buffer = np.roll(audio_buffer, -len(new_audio))
                    audio_buffer[-len(new_audio):] = new_audio

                # Transcribe if there's signal
                rms = float(np.sqrt(np.mean(audio_buffer[-SAMPLE_RATE:] ** 2)))
                if rms > 0.003:
                    text = self._transcribe(audio_buffer)
                    if text and text != last_whisper_text:
                        prev = last_whisper_text
                        last_whisper_text = text
                        self.on_partial(text)

                        # Only append the NEW words at the end of the transcription
                        # Whisper rewrites the whole buffer each tick -- we extract
                        # just the tail that wasn't in the previous transcription
                        new_words = _extract_new_tail(prev, text)
                        if new_words:
                            with self._transcript_lock:
                                # Strip trailing ? from partial chunks -- Whisper adds
                                # them mid-sentence and they break the transcript structure
                                if self._transcript:
                                    # Remove trailing ? from previous entry before appending
                                    self._transcript = self._transcript.rstrip("?").rstrip()
                                    self._transcript += " " + new_words
                                else:
                                    self._transcript = new_words

            # Every CHECK_INTERVAL seconds, ask Claude what to do
            if now >= next_check_at:
                next_check_at = now + CHECK_INTERVAL
                with self._transcript_lock:
                    current = self._transcript

                if current and not answering.locked():
                    threading.Thread(
                        target=self._ask_claude,
                        args=(current, answering),
                        daemon=True
                    ).start()

            time.sleep(0.05)

    def _ask_claude(self, transcript: str, lock: threading.Lock):
        if not lock.acquire(blocking=False):
            return
        try:
            self.on_status("Checking transcript…")
            from openai import OpenAI

            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )

            job_section = f"\n\n[JOB DESCRIPTION]\n{self.job_text}" if self.job_text else ""
            full_system = f"""{SYSTEM_PROMPT}

[CANDIDATE CV]
{self.cv_text}

[CANDIDATE TONE GUIDE]
{self.tone_content}{job_section}

[CRITICAL RULES -- NON-NEGOTIABLE]
1. NEVER open with a negative or qualification. The first word of every answer must be positive and owning.
   BANNED OPENINGS: "I haven't...", "I don't have formal...", "Not in the traditional sense...", "While I haven't...", "I didn't formally..."
   These phrases will cost the candidate the job. Never use them.

2. If the CV shows ANY relevant experience -- the answer is YES, full stop. Then explain with specifics.
   - "Have you managed a team?" → The CV shows founding engineer who coordinated designers, product, contractors, mentored juniors, owned delivery. The answer is YES.
   - Lead with the YES energy, then back it with the real story.

3. Own the experience completely. Do not spin, qualify, or hedge. The candidate has done real things -- state them directly."""

            # Only send the latest unanswered segment to Claude
            # Everything before [ANSWERED] is done -- slice it out entirely
            parts = transcript.split("[ANSWERED]")
            latest_segment = parts[-1].strip()

            # Strip thinking fillers before sending to Claude
            import re
            latest_segment = re.sub(
                r'\b(um+|uh+|em+|ah+|er+|hmm+|mhm+|erm+)\b',
                '', latest_segment, flags=re.IGNORECASE
            )
            latest_segment = re.sub(r' {2,}', ' ', latest_segment).strip()

            # Also trim the in-memory transcript to just the latest segment
            # so it doesn't grow forever with answered content
            with self._transcript_lock:
                self._transcript = latest_segment

            self.on_status(f"TRANSCRIPT SENT: {latest_segment[:200]}")
            response = client.chat.completions.create(
                model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
                max_tokens=500,
                stream=False,
                messages=[
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": f"LATEST INTERVIEW SEGMENT (raw speech recognition -- may be noisy):\n{latest_segment}\n\nIf you can identify a question, format your response as:\nQUESTION: <the clean predicted question>\nANSWER: <your answer>\n\nIf not, reply with just: WAITING"}
                ],
                extra_headers={
                    "HTTP-Referer": "https://interview-assistant.local",
                    "X-Title": "AI Interview Assistant",
                },
            )

            reply = response.choices[0].message.content.strip()
            self.on_status(f"Claude: {reply[:60]}…" if len(reply) > 60 else f"Claude: {reply}")

            if reply == "WAITING" or reply.startswith("WAITING"):
                self.on_status("Listening… (waiting for complete question)")
                return

            # Parse QUESTION/ANSWER format
            predicted_question = self._extract_last_question(transcript)
            answer = reply
            if "QUESTION:" in reply and "ANSWER:" in reply:
                try:
                    q_part = reply.split("ANSWER:")[0].replace("QUESTION:", "").strip()
                    a_part = reply.split("ANSWER:")[1].strip()
                    predicted_question = q_part
                    answer = a_part
                except Exception:
                    pass

            last_question = predicted_question

            # Mark it as answered and set a cooldown
            # so the candidate speaking their answer doesn't re-trigger
            with self._transcript_lock:
                self._transcript = ""  # wipe transcript clean after answer
            

            self.on_answer(last_question, answer)
            self.on_status("Listening…")

        except Exception as e:
            self.on_status(f"❌ Claude error: {e}")
        finally:
            lock.release()

    def _extract_last_question(self, transcript: str) -> str:
        """Pull the last unanswered segment from the transcript."""
        parts = transcript.split("[ANSWERED]")
        last = parts[-1].strip()
        # Return last sentence-ish chunk
        sentences = [s.strip() for s in last.replace("?", "?.").split(".") if s.strip()]
        return sentences[-1] if sentences else last

    def _transcribe(self, audio: np.ndarray) -> str:
        try:
            segments, _ = self._model.transcribe(
                audio,
                language="en",
                beam_size=1,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 200},
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception:
            return ""