import sys
import time
import numpy as np
from audio_capture import AudioCapture, list_microphone_devices

device_index = int(sys.argv[1]) if len(sys.argv) > 1 else 1
mics = list_microphone_devices()
name = next((d["name"] for d in mics if d["index"] == device_index), f"device [{device_index}]")
print(f"\n🎤 Testing [{device_index}]: {name}")
print("Speak now for 7 seconds...\n")

chunks = []
def on_chunk(audio):
    chunks.append(audio)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    bar = "█" * int(rms * 400)
    print(f"  RMS: {rms:.4f}  {bar if bar else '(silence)'}")

cap = AudioCapture(device_index=device_index, on_audio_chunk=on_chunk, source="microphone", chunk_seconds=3)
cap.start()
time.sleep(7)
cap.stop()
if chunks:
    avg = float(np.mean([np.sqrt(np.mean(c**2)) for c in chunks]))
    print(f"{'✅ Good signal' if avg > 0.001 else '⚠️  Very low signal'} — avg RMS: {avg:.4f}")
else:
    print("❌ No chunks received")