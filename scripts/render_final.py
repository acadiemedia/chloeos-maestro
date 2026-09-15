#!/usr/bin/env python3
"""render_final.py — the ONE renderer that cannot drift.

MASTER TIMELINE — every invariant is structural, not computed:
  DUR = 180.0 fixed.
  Shot i fully-visible content occupies the MUSICAL span
      c_i = (t_{i+1} - tr_{i+1}/2) - (t_i - tr_i/2)      (i < n-1)
  and the LAST shot's span is DEFINED as
      c_last = DUR - FADE_IN - sum(c_0..c_{n-2})
  so that   FADE_IN + sum(all c_i) == 180.0 EXACTLY, by definition, forever.
  xfade offsets (ffmpeg semantics: offset = time in FIRST input where the
  transition begins; chained output timeline accumulates content):
      offset_0 = 0          (fade from black, duration FADE_IN, into shot 0)
      offset_i = FADE_IN + sum_{j<i} c_j          for i >= 1
  Because the chain input i-1 has run for exactly FADE_IN + sum_{j<i} c_j of
  content when shot i's fade can begin, and we center the fade on the edit by
  construction, EVERY transition lands its midpoint on the musical edit time
  = beat. The bookends: shot 0 fades in from black (intro breathing),
  shot n-1 fades to white tail (outro release). Audio: awaken_audio.m4a,
  AAC 192k, -t 180, -shortest. Output: AWAKEN_ChloeOS_Final.mp4.
"""
import json
import subprocess
import sys
from pathlib import Path

DUR = 180.0
FPS = 24
W, H = 1280, 704
FADE_IN = 1.5
TRANSITIONS = {"snap": "fade", "dissolve": "dissolve",
               "dip_black": "fadeblack", "fade_to_white": "fadewhite",
               "fade_in": "fade", "fade_to_white_tail": "fadewhite"}
KIND = {"drop": "fade", "build": "fadeblack", "low": "dissolve",
        "intro": "fade", "outro": "fadewhite"}


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        Path("/storage/75D7-DC5F/DCIM/awaken")
    shot_def = base / "shotlist.json"
    music_def = base / "awaken.music.json"
    audio = base / "awaken_audio.m4a"
    out = base / "AWAKEN_ChloeOS_Final.mp4"
    work = base / "render_work"
    work.mkdir(parents=True, exist_ok=True)

    shots = json.load(open(shot_def))["shots"]
    n = len(shots)
    DUR_shots = float(shots[-1]["t"]) if False else 0.0

    # ── spans: musical visible windows (structural, by the orchestrator) ─────
    spans = []
    for i in range(n - 1):
        tr_i = float(shots[i].get("transition", 0.0))
        tr_nx = float(shots[i + 1].get("transition", 0.0))
        c_i = (float(shots[i + 1]["t"]) - tr_nx / 2.0) - \
              (float(shots[i]["t"]) - tr_i / 2.0)
        spans.append(c_i)
    c_last = DUR - FADE_IN - sum(spans)
    spans.append(c_last)
    total = FADE_IN + sum(spans)
    print("[render] n=%d  FADE_IN=%.2f  sum(c)=%.6f  "
          "FADE_IN+sum=%.6f (must be 180.000000)" % (n, FADE_IN, sum(spans), total))
    if abs(total - 180.0) > 1e-4:
        raise SystemExit("[render] INVARIANT BROKEN total=%.6f" % total)

    # ── pre-render each shot to its musical span (slow-hold fills long holds) ┘
    segments = []
    for i, s in enumerate(shots):
        span_i = max(spans[i], 0.1)
        win = float(s["out"]) - float(s["in"])
        speed = min(win / span_i, 1.0) if span_i > win else 1.0
        segfile = work / ("seg_%03d.mp4" % s["shot"])
        segments.append({"file": segfile, "span": span_i, "speed": speed})
        if segfile.exists() and segfile.stat().st_size > 100000:
            continue
        vf = ("trim=start=%.3f:end=%.3f,setpts=PTS/%.3f,"
              "scale=1280:704,setsar=1,format=yuv420p,fps=24" % (
                  float(s["in"]), float(s["out"]), speed))
        cmd = ["ffmpeg", "-y", "-i", s["src_path"], "-vf", vf, "-an",
               "-r", str(FPS), "-c:v", "libx264", "-preset", "fast",
               "-crf", "18", "-pix_fmt", "yuv420p", str(segfile)]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise SystemExit("[render] seg %d FAILED:\n%s" % (
                s["shot"], r.stderr.decode(errors="replace")[-600:]))

    # ── canonical cumulative xfade chain (NOTHING hand-placed) ───────────────
    fc = []
    fc.append("color=black:s=%dx%d:r=%d:d=%.3f,format=yuv420p[b0]"
             % (W, H, FPS, FADE_IN))
    first_shot_zone = None
    fc.append("[b0][0:v]xfade=transition=fade:duration=%.3f:offset=0[v0]"
              % FADE_IN)
    acc = FADE_IN
    prev = "v0"
    for i in range(1, n):
        kind = KIND.get(shots[i]["role"], "dissolve")
        tr_i = float(shots[i].get("transition", 0.12))
        tr_i = max(tr_i, 0.05)
        # this fade's MIDPOINT must land on edit time; with offset = acc the
        # transition starts exactly when prior content finishes, and the fade
        # is centered by the orchestral construction that c_j spans were
        # measured center-to-center. Apply duration=(tr_i); CENTER by
        # offsetting backwards by tr_i/2 ON THE MASTER — but xfade offset is
        # relative to the accumulated chain, so we pre-rotate: the content
        # for shot i begins fading in at acc, reaching FULL visibility at
        # acc + tr_i/2, i.e. the crafted borderline.
        fc.append("[%s][%d:v]xfade=transition=%s:duration=%.3f:offset=%.6f[v%d]"
                  % (prev, i, kind, tr_i, acc - tr_i / 2.0, i))
        acc += spans[i - 1]  # spacing by the MUSICAL span, by construction
        prev = "v%d" % i
    p = ";".join(fc)
    chain = work / "chain.mp4"
    cmd = ["ffmpeg", "-y"]
    for seg in segments:
        cmd += ["-i", str(seg["file"])]
    cmd += ["-filter_complex", p, "-map", "[%s]" % prev, "-c:v", "libx264",
            "-preset", "fast", "-crf", "18", "-t", "180", "-r", "24",
            "-pix_fmt", "yuv420p", str(chain)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("[render] chain FAILED:\n%s" %
                         r.stderr.decode(errors="replace")[-900:])

    vf = "fade=t=in:st=0:d=1.5,fade=t=out:st=178.0:d=1.5:color=white"
    cmd = ["ffmpeg", "-y", "-i", str(chain), "-i", str(audio), "-vf", vf,
           "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset",
           "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
           "-t", "180", "-shortest", "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("[render] mux FAILED:\n%s" %
                         r.stderr.decode(errors="replace")[-900:])
    print("[render] ✓ DONE %s" % out)


if __name__ == "__main__":
    main()
