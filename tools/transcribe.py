"""Word-level transcription: python3 tools/transcribe.py audio16k.wav transcript.json [model]"""
import sys, json, time, wave
import numpy as np
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
model_name = sys.argv[3] if len(sys.argv) > 3 else "small.en"
t0 = time.time()
m = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4)
w = wave.open(src)
audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
segs, info = m.transcribe(audio, language="en", word_timestamps=True, vad_filter=True,
                          beam_size=1, condition_on_previous_text=False)
res = []
for s in segs:
    res.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                "words": [{"s": w.start, "e": w.end, "w": w.word} for w in (s.words or [])]})
    if len(res) % 50 == 0:
        print(f"{s.end/60:.1f} min transcribed, {time.time()-t0:.0f}s elapsed", flush=True)
        json.dump(res, open(out, "w"))
json.dump(res, open(out, "w"))
print("DONE", len(res), "segments", f"{time.time()-t0:.0f}s")
