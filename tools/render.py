"""Render a vertical 1080x1920 clip from a stream segment using a JSON spec.

python3 tools/render.py spec.json

Spec fields:
  source      path to the 16:9 source video (a downloaded section of the stream)
  src_offset  stream time (s) that corresponds to t=0 of `source`
  start, end  stream time (s) of the clip
  parts       list of {"to": stream_time, "mode": "split"|"cam"|"game", ...}
              consecutive; each part ends at "to" (last one may omit it).
              split: cam box on top (40%), game box below (60%)
                     "cam": [x,y,w,h] source px of webcam overlay
                     "game": [x,y,w,h] source px of gameplay crop (optional; default centre)
              cam:   whole frame is webcam; "cx" = centre x (source px) of the 9:16 crop
              game:  fullscreen gameplay; "cx" = centre x of the 9:16 crop
  transcript  path to transcript.json (word timestamps in stream time)
  keywords    list of words to colour yellow
  hook        hook text (caps), shown first `hook_dur` seconds
  handle      e.g. "@bendadonnn"
  sub_y       y of subtitle centre for split (default 768 = junction)
  sub_y_full  y of subtitle centre for cam/game modes (default 1250)
  font        font name (default Anton)
  out         output path
"""
import json, subprocess, sys, os, re

W, H, FPS = 1080, 1920, 30
CAM_H = 768            # 40% of 1920
GAME_H = H - CAM_H     # 1152
CENSOR = {"nigga": "N*GGA", "nigger": "N*GGA", "motherfuck": "M*THAF*CKIN", "fuck": "F*CK", "bitch": "B*TCH"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "assets", "fonts")


def even(v):
    return int(round(v / 2.0)) * 2


def crop_to_aspect(box, aspect, cx=None):
    """Shrink [x,y,w,h] to the target aspect (w/h), centred on cx if given."""
    x, y, w, h = box
    if w / h > aspect:
        nw = h * aspect
        c = cx if cx is not None else x + w / 2
        nx = min(max(c - nw / 2, x), x + w - nw)
        return [even(nx), even(y), even(nw), even(h)]
    nh = w / aspect
    return [even(x), even(y + (h - nh) / 2), even(w), even(nh)]


def part_filter(i, p, sw, sh):
    mode = p["mode"]
    if mode == "split":
        ch = even(p.get("cam_h", CAM_H)); gh = H - ch
        cam = crop_to_aspect(p["cam"], W / ch, p.get("cam_cx"))
        g = p.get("game") or [0, 0, sw, sh]
        game = crop_to_aspect(g, W / gh, p.get("game_cx", g[0] + g[2] / 2))
        return (f"[v{i}]split[c{i}][g{i}];"
                f"[c{i}]crop={cam[2]}:{cam[3]}:{cam[0]}:{cam[1]},scale={W}:{ch}:flags=lanczos,setsar=1[ct{i}];"
                f"[g{i}]crop={game[2]}:{game[3]}:{game[0]}:{game[1]},scale={W}:{gh}:flags=lanczos,setsar=1[gt{i}];"
                f"[ct{i}][gt{i}]vstack[o{i}];")
    box = p.get("box") or [0, 0, sw, sh]
    c = crop_to_aspect(box, W / H, p.get("cx"))
    return (f"[v{i}]crop={c[2]}:{c[3]}:{c[0]}:{c[1]},scale={W}:{H}:flags=lanczos,setsar=1[o{i}];")


def ass_time(t):
    t = max(t, 0)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(spec, words, part_modes):
    font = spec.get("font", "Anton")
    sub_y = spec.get("sub_y", 768)
    sub_y_full = spec.get("sub_y_full", 1250)
    hook_y = spec.get("hook_y", 230)
    kw = {k.lower() for k in spec.get("keywords", [])}
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{font},{spec.get('word_size',150)},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,10,5,5,40,40,0,1
Style: Hook,{font},{spec.get('hook_size',104)},&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,1,0,3,22,0,5,60,60,0,1
Style: Handle,{font},44,&H40FFFFFF,&H40FFFFFF,&H80000000,&H00000000,0,0,0,0,100,100,1,0,1,3,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    dur = spec["end"] - spec["start"]
    hook = spec.get("hook")
    if hook:
        hd = spec.get("hook_dur", 2.5)
        ev.append(f"Dialogue: 2,{ass_time(0)},{ass_time(hd)},Hook,,0,0,0,,"
                  f"{{\\pos({W//2},{hook_y})\\fad(0,150)}}{hook}")
    if spec.get("handle"):
        ev.append(f"Dialogue: 1,{ass_time(0)},{ass_time(dur)},Handle,,0,0,0,,"
                  f"{{\\pos({W//2},{spec.get('handle_y', 1640)})}}{spec['handle']}")

    for tx in spec.get("texts", []):
        ev.append(f"Dialogue: 2,{ass_time(tx['t0'])},{ass_time(tx['t1'])},Hook,,0,0,0,,"
                  f"{{\\pos({W//2},{tx.get('y', 960)})}}{tx['text']}")

    def mode_at(t):
        for a, b, m in part_modes:
            if a <= t < b:
                return m
        return part_modes[-1][2]

    for k, w in enumerate(words):
        s = w["s"] - spec["start"]
        e = (words[k + 1]["s"] - spec["start"]) if k + 1 < len(words) else w["e"] - spec["start"]
        e = min(e, w["e"] - spec["start"] + 0.6)
        if e <= 0 or s >= dur:
            continue
        s, e = max(s, 0), min(e, dur)
        if e - s < 0.08:
            e = s + 0.08
        text = w["w"].strip().upper().rstrip(".,;:").replace("...", "")
        bare = re.sub(r"[^\w']", "", text).lower()
        for a, b in CENSOR.items():
            if bare.startswith(a):
                text = b
                break
        if not bare:
            continue
        y = sub_y if mode_at(s) == "split" else sub_y_full
        col = "{\\c&H00D7FF&}" if bare in kw else ""
        pop = "{\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}"
        ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Word,,0,0,0,,"
                  f"{{\\pos({W//2},{y})}}{pop}{col}{text}")
    return head + "\n".join(ev) + "\n"


def main():
    spec = json.load(open(sys.argv[1]))
    src = spec["source"]
    off = spec.get("src_offset", 0.0)
    probe = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "json", src]))["streams"][0]
    sw, sh = probe["width"], probe["height"]

    words = []
    segs = [] if "words" in spec else json.load(open(spec["transcript"]))
    if "words" in spec:
        words = [dict(w) for w in spec["words"]]
    for seg in segs:
        if seg["end"] < spec["start"] or seg["start"] > spec["end"]:
            continue
        for w in seg["words"]:
            if w["s"] >= spec["start"] - 0.05 and w["s"] < spec["end"]:
                words.append(w)
    drop = {float(x) for x in spec.get("drop_words", [])}
    words = [w for w in words if not any(abs(w["s"] - d) < 0.05 for d in drop)]
    for k, v in spec.get("word_fix", {}).items():
        for w in words:
            if abs(w["s"] - float(k)) < 0.05:
                w["w"] = v
    words = [w for w in words if w["w"].strip()]

    # fast input seek: jump close to the clip start, then trim precisely
    pre = max(0.0, spec["start"] - off - 3.0)
    off = off + pre
    parts, t = [], spec["start"]
    for p in spec["parts"]:
        to = min(p.get("to", spec["end"]), spec["end"])
        parts.append((t, to, p))
        t = to
    part_modes = [(a - spec["start"], b - spec["start"], p["mode"]) for a, b, p in parts]

    ass_path = os.path.splitext(spec["out"])[0] + ".ass"
    open(ass_path, "w").write(build_ass(spec, words, part_modes))

    fc = f"[0:v]fps={FPS},split={len(parts)}" + "".join(f"[s{i}]" for i in range(len(parts))) + ";"
    for i, (a, b, p) in enumerate(parts):
        fc += f"[s{i}]trim={a-off:.3f}:{b-off:.3f},setpts=PTS-STARTPTS[v{i}];"
        fc += part_filter(i, p, sw, sh)
    fc += "".join(f"[o{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=0[cat];"
    fc += f"[cat]ass={ass_path}:fontsdir={FONTS}[vout];"
    # two-pass loudness normalisation to -14 LUFS (skipped for multi-segment builds)
    atr = f"atrim={spec['start']-off:.3f}:{spec['end']-off:.3f},asetpts=PTS-STARTPTS"
    if spec.get("no_loudnorm"):
        meas = None
    else:
        meas = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{pre:.3f}", "-i", src, "-af",
                           atr + ",loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-vn", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    if meas is None:
        ln = "anull"
    else:
        m = json.loads(meas[meas.rfind("{"):meas.rfind("}") + 1])
        ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    fc += (f"[0:a]atrim={spec['start']-off:.3f}:{spec['end']-off:.3f},asetpts=PTS-STARTPTS,"
           f"{ln},aresample=48000,"
           f"afade=t=out:st={spec['end']-spec['start']-0.15:.3f}:d=0.15[aout]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{pre:.3f}", "-i", src, "-filter_complex", fc,
           "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", spec["out"]]
    subprocess.run(cmd, check=True)
    print("rendered", spec["out"])


if __name__ == "__main__":
    main()
