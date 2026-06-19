"""
audio_capture.py — Captures audio from microphone or WASAPI loopback (system audio).

On Windows, WASAPI loopback lets you capture everything playing through the speakers —
including the interviewer's voice over Zoom, Google Meet, Teams, etc.

Usage:
    from audio_capture import AudioCapture, list_loopback_devices

    # List available loopback devices
    devices = list_loopback_devices()

    # Capture system audio and feed chunks to a callback
    capture = AudioCapture(device_index=devices[0]['index'], on_audio_chunk=my_callback)
    capture.start()
    # ... later ...
    capture.stop()
"""

import threading
import numpy as np
from typing import Callable, List, Dict, Optional

SAMPLE_RATE = 16000   # 16kHz — what Whisper expects
CHANNELS = 1          # mono
CHUNK_SECONDS = 1     # how many seconds of audio per chunk sent to transcriber
DTYPE = "float32"


def list_loopback_devices() -> List[Dict]:
    """
    Return a list of available WASAPI loopback devices (system audio sources).
    These are the devices that capture what's playing through your speakers.

    Falls back to listing all input devices if pyaudiowpatch isn't available.
    """
    devices = []

    try:
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                if info.get("isLoopbackDevice", False):
                    devices.append({
                        "index": i,
                        "name": info["name"],
                        "source": "loopback",
                        "channels": info["maxInputChannels"],
                        "sample_rate": int(info["defaultSampleRate"]),
                    })
            except Exception:
                continue
        p.terminate()

    except ImportError:
        # pyaudiowpatch not installed — fall back to sounddevice
        pass

    return devices


def list_microphone_devices() -> List[Dict]:
    """Return a list of available microphone (input) devices."""
    import sounddevice as sd
    devices = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({
                "index": i,
                "name": dev["name"],
                "source": "microphone",
                "channels": dev["max_input_channels"],
                "sample_rate": int(dev["default_samplerate"]),
            })
    return devices


def list_all_input_devices() -> List[Dict]:
    """Return all input devices (loopback + microphones)."""
    loopback = list_loopback_devices()
    mics = list_microphone_devices()
    return loopback + mics


class AudioCapture:
    """
    Continuously captures audio from a device and feeds overlapping chunks
    to a callback function for transcription.

    Uses a rolling buffer so we don't lose words at chunk boundaries.

    Args:
        device_index:    Index of the audio device to capture from.
        on_audio_chunk:  Callback receiving a numpy float32 array at 16kHz.
        source:          "loopback" (system audio) or "microphone".
        chunk_seconds:   How many seconds per chunk sent to transcriber.
    """

    def __init__(
        self,
        device_index: int,
        on_audio_chunk: Callable[[np.ndarray], None],
        source: str = "loopback",
        chunk_seconds: int = CHUNK_SECONDS,
    ):
        self.device_index = device_index
        self.on_audio_chunk = on_audio_chunk
        self.source = source
        self.chunk_seconds = chunk_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start capturing audio in a background thread."""
        self._stop_event.clear()
        if self.source == "loopback":
            self._thread = threading.Thread(target=self._capture_loopback, daemon=True)
        else:
            self._thread = threading.Thread(target=self._capture_microphone, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the capture thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _capture_loopback(self):
        """Capture WASAPI loopback audio using pyaudiowpatch."""
        try:
            import pyaudiowpatch as pyaudio
        except ImportError:
            raise ImportError(
                "pyaudiowpatch is required for system audio capture.\n"
                "Install it with: pip install pyaudiowpatch"
            )

        p = pyaudio.PyAudio()
        chunk_frames = self.chunk_seconds * SAMPLE_RATE
        raw_chunk_size = 1024  # frames per PyAudio read call
        buffer = []

        try:
            device_info = p.get_device_info_by_index(self.device_index)
            native_rate = int(device_info["defaultSampleRate"])
            native_channels = device_info["maxInputChannels"]

            stream = p.open(
                format=pyaudio.paFloat32,
                channels=native_channels,
                rate=native_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=raw_chunk_size,
            )

            while not self._stop_event.is_set():
                raw = stream.read(raw_chunk_size, exception_on_overflow=False)
                audio = np.frombuffer(raw, dtype=np.float32)

                # Mix down to mono if needed
                if native_channels > 1:
                    audio = audio.reshape(-1, native_channels).mean(axis=1)

                # Resample to 16kHz if needed
                if native_rate != SAMPLE_RATE:
                    audio = _resample(audio, native_rate, SAMPLE_RATE)

                buffer.extend(audio.tolist())

                # Send a chunk when we've accumulated enough
                if len(buffer) >= chunk_frames:
                    chunk = np.array(buffer[:chunk_frames], dtype=np.float32)
                    self.on_audio_chunk(chunk)
                    # Overlap: keep the last 1 second so we don't cut words
                    buffer = buffer[SAMPLE_RATE:]

            stream.stop_stream()
            stream.close()

        finally:
            p.terminate()

    def _capture_microphone(self):
        """Capture microphone audio, letting sounddevice resample to 16kHz directly."""
        import sounddevice as sd

        # Ask sounddevice to deliver audio at exactly 16kHz — it handles resampling
        # internally using PortAudio, which is more reliable than our manual approach.
        buffer = []
        chunk_frames = self.chunk_seconds * SAMPLE_RATE

        def callback(indata, frames, time, status):
            # Mix to mono if needed
            if indata.shape[1] > 1:
                audio = indata.mean(axis=1).astype(np.float32)
            else:
                audio = indata[:, 0].astype(np.float32)

            buffer.extend(audio.tolist())

            if len(buffer) >= chunk_frames:
                chunk = np.array(buffer[:chunk_frames], dtype=np.float32)
                self.on_audio_chunk(chunk)
                # keep 0.5s overlap
                buffer.clear()
                buffer.extend(chunk[-SAMPLE_RATE // 2:].tolist())

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=DTYPE,
            device=self.device_index,
            callback=callback,
            blocksize=512,
        ):
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=0.1)


def _resample(audio: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """Simple linear interpolation resample. Good enough for speech."""
    if from_rate == to_rate:
        return audio
    duration = len(audio) / from_rate
    target_length = int(duration * to_rate)
    indices = np.linspace(0, len(audio) - 1, target_length)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time

    print("🎙  Audio Capture — Device Listing Test\n")

    print("WASAPI Loopback devices (system audio):")
    loopback = list_loopback_devices()
    if loopback:
        for d in loopback:
            print(f"  [{d['index']}] {d['name']} ({d['sample_rate']}Hz)")
    else:
        print("  (none found — pyaudiowpatch may not be installed)")

    print("\nMicrophone devices:")
    mics = list_microphone_devices()
    for d in mics:
        print(f"  [{d['index']}] {d['name']}")

    # Quick 3-second mic capture test
    if mics:
        print(f"\n🎤 Capturing 3 seconds from mic [{mics[0]['index']}]: {mics[0]['name']}")
        chunks_received = []

        def on_chunk(audio: np.ndarray):
            chunks_received.append(audio)
            rms = float(np.sqrt(np.mean(audio ** 2)))
            print(f"   Chunk received: {len(audio)} samples, RMS volume: {rms:.4f}")

        cap = AudioCapture(
            device_index=mics[0]["index"],
            on_audio_chunk=on_chunk,
            source="microphone",
            chunk_seconds=3,
        )
        cap.start()
        time.sleep(5)
        cap.stop()
        print(f"\n✅ Received {len(chunks_received)} chunk(s)")


def _test_device(device_index: int):
    """Quick RMS test for a specific device index."""
    import time
    mics = list_microphone_devices()
    name = next((d["name"] for d in mics if d["index"] == device_index), f"device [{device_index}]")
    print(f"\n🎤 Testing device [{device_index}]: {name}")
    print("   Make some noise or speak now...\n")
    chunks = []

    def on_chunk(audio):
        chunks.append(audio)
        rms = float(np.sqrt(np.mean(audio ** 2)))
        bar = "█" * int(rms * 400)
        print(f"   RMS: {rms:.4f}  {bar if bar else '(silence)'}")

    cap = AudioCapture(device_index=device_index, on_audio_chunk=on_chunk, source="microphone", chunk_seconds=3)
    cap.start()
    time.sleep(7)
    cap.stop()
    if chunks:
        avg = float(np.mean([np.sqrt(np.mean(c**2)) for c in chunks]))
        print(f"\n{'✅ Good signal' if avg > 0.001 else '⚠️  Very low signal'} — avg RMS: {avg:.4f}")
    else:
        print("\n❌ No audio received")


if __name__ == "__main__" and len(sys.argv) > 1:
    import sys
    _test_device(int(sys.argv[1]))