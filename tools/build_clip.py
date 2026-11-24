"""Build one clip from several stream moments (jump cuts).

python3 tools/build_clip.py clip.json

clip.json: {"out": "clips/clip_01.mp4", "common": {...render.py fields shared by all segments...},
            "segments": [{...render.py fields for this segment...}, ...]}
Each segment is rendered by render.py without loudness normalisation, then the
pieces are concatenated and the audio is normalised to -14 LUFS in two passes.
The hook from `common`/segment 0 is shown only on the first segment.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = json.load(open(sys.argv[1]))
out = spec["out"]
base = os.path.splitext(out)[0]
pieces = []
for i, seg in enumerate(spec["segments"]):
    s = dict(spec.get("common", {}))
    s.update(seg)
    if i > 0:
        s.pop("hook", None)
    s["no_loudnorm"] = True
    s["out"] = f"{base}_seg{i}.mp4"
    p = f"{base}_seg{i}.json"
    json.dump(s, open(p, "w"), indent=1)
    subprocess.run([sys.executable, os.path.join(HERE, "render.py"), p], check=True)
    pieces.append(s["out"])

lst = base + "_concat.txt"
open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in pieces))
joined = base + "_joined.mp4"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", joined, "-af",
                       "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-vn", "-f", "null", "-"],
                      capture_output=True, text=True).stderr
m = json.loads(meas[meas.rfind("{"):meas.rfind("}") + 1])
ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", joined, "-c:v", "copy", "-af", ln + ",aresample=48000",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
for x in pieces + [joined, lst]:
    os.remove(x)
print("built", out)
