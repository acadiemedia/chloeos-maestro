#!/usr/bin/env python3
"""render_final.py — Deterministic beat-locked film compiler.

Constructs an exact 180.000000s master video with zero timeline drift.
Pre-renders/trims segments, normalizes timebases (1/24), builds the cumulative
xfade chain via filter_complex_script, and muxes master audio.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

DUR = 180.0
FPS = 24
W, H = 1280, 704
FADE_IN = 1.5

KIND = {
    "drop": "fade",
    "build": "fadeblack",
    "low": "dissolve",
    "intro": "fade",
    "bridge": "dissolve",
    "outro": "fadewhite"
}

def get_ffmpeg():
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    local_ff = Path(r"X:\ffmpeg\bin\ffmpeg.exe")
    if local_ff.exists():
        return str(local_ff)
    return "ffmpeg"

def render_film(song_dir: Path, output_file: Path = None, shotlist_file: Path = None, work_dir: Path = None):
    ffmpeg_bin = get_ffmpeg()
    shot_def = shotlist_file or (song_dir / "shotlist.json")
    mastered = list(song_dir.glob("*_mastered.wav"))
    if mastered:
        audio_file = mastered[0]
    else:
        audio_file = next(song_dir.glob("*.wav"), None) or next(song_dir.glob("*.m4a"), None) or next(song_dir.glob("*.mp3"), None)

    if not shot_def.exists():
        sys.exit(f"Missing {shot_def}")
    if not audio_file or not audio_file.exists():
        sys.exit(f"Missing audio file in {song_dir}")

    if not output_file:
        slug = song_dir.name.replace("-", "_")
        output_file = song_dir / f"{slug.title()}_ChloeOS_Final.mp4"

    work = work_dir or (song_dir / "render_work")
    work.mkdir(parents=True, exist_ok=True)

    shots = json.load(open(shot_def, encoding="utf-8"))["shots"]
    n = len(shots)

    # ── 1. Calculate exact transition offsets and segment durations ──────────
    offsets = [0.0] * n
    seg_durs = [0.0] * n

    for i in range(1, n):
        tr_i = float(shots[i].get("transition", 0.12))
        t_cut = float(shots[i]["t_start"])
        offsets[i] = round(t_cut - tr_i / 2.0, 6)

    # Shot 0 runs from 0 to first transition + padding
    seg_durs[0] = round(offsets[1] + float(shots[1].get("transition", 0.9)) + 0.5, 3)

    for i in range(1, n - 1):
        tr_next = float(shots[i + 1].get("transition", 0.12))
        # Segment needs to play from offset_i to offset_{i+1} + tr_{i+1}
        needed = (offsets[i + 1] + tr_next + 0.5) - offsets[i]
        seg_durs[i] = round(needed, 3)

    # Final shot span is mathematically defined so total == DUR
    seg_durs[-1] = round(DUR - offsets[-1], 6)

    print(f"[render] n={n} shots. Master duration target: {DUR:.3f}s")
    print(f"  Final shot offset: {offsets[-1]:.3f}s, duration: {seg_durs[-1]:.3f}s -> End: {offsets[-1] + seg_durs[-1]:.3f}s")

    # ── 2. Pre-render segments ───────────────────────────────────────────────
    segments = []
    for i, s in enumerate(shots):
        req_dur = seg_durs[i]
        segfile = work / f"seg_{s['shot']:03d}.mp4"
        src_path = s.get("clip_path")

        if not src_path or not Path(src_path).exists():
            clean_txt = "".join(c for c in s.get("lyric", "")[:40] if c.isalnum() or c in " .,-?!")
            vf = (f"color=c=0x0a1420:s={W}x{H}:r={FPS}:d={req_dur:.3f},"
                  f"drawtext=text='SHOT {s['shot']:03d} [{s['role'].upper()}]':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=(h-text_h)/2-40,"
                  f"drawtext=text='{clean_txt}':fontcolor=0x40e0d0:fontsize=28:x=(w-text_w)/2:y=(h-text_h)/2+30,"
                  f"format=yuv420p,fps={FPS}")
            cmd = [ffmpeg_bin, "-y", "-f", "lavfi", "-i", vf, "-t", f"{req_dur:.3f}",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(segfile)]
            subprocess.run(cmd, capture_output=True)
        else:
            vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,format=yuv420p,fps={FPS},tpad=stop_mode=clone:stop=-1"
            cmd = [ffmpeg_bin, "-y", "-i", src_path, "-vf", vf, "-an",
                   "-t", f"{req_dur:.3f}", "-c:v", "libx264", "-preset", "fast",
                   "-crf", "18", "-pix_fmt", "yuv420p", str(segfile)]
            subprocess.run(cmd, capture_output=True)

        segments.append({"file": segfile, "dur": req_dur})

    # ── 3. Build filter_complex_script ───────────────────────────────────────
    fc = [f"color=black:s={W}x{H}:r={FPS}:d={FADE_IN:.3f},format=yuv420p,settb=1/{FPS}[b0];\n"]
    for i in range(n):
        fc.append(f"[{i}:v]settb=1/{FPS},fps={FPS}[vin{i}];\n")

    fc.append(f"[b0][vin0]xfade=transition=fade:duration={FADE_IN:.3f}:offset=0[v0];\n")
    prev = "v0"

    for i in range(1, n):
        kind = KIND.get(shots[i]["role"], "dissolve")
        tr_i = float(shots[i].get("transition", 0.12))
        tr_i = max(tr_i, 0.05)
        offset = offsets[i]
        fc.append(f"[{prev}][vin{i}]xfade=transition={kind}:duration={tr_i:.3f}:offset={offset:.6f}[v{i}];\n")
        prev = f"v{i}"

    fc[-1] = fc[-1].rstrip(";\n")
    script_file = work / "filter_complex.txt"
    script_file.write_text("".join(fc), encoding="utf-8")

    chain = work / "chain.mp4"
    cmd = [ffmpeg_bin, "-y"]
    for seg in segments:
        cmd += ["-i", str(seg["file"])]
    cmd += ["-filter_complex_script", str(script_file), "-map", f"[{prev}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-t", f"{DUR:.3f}", "-r", str(FPS),
            "-pix_fmt", "yuv420p", str(chain)]

    print(f"[render] Compiling video chain ({n} shots)...")
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"[render] Chain compilation failed:\n{r.stderr.decode('utf-8', 'replace')[-800:]}")

    # ── 4. Final audio mux & tail fade ───────────────────────────────────────
    print("[render] Muxing audio & applying master color fades...")
    vf = f"fade=t=in:st=0:d=1.5,fade=t=out:st={DUR-2.0:.1f}:d=2.0:color=white"
    mux_cmd = [
        ffmpeg_bin, "-y", "-i", str(chain), "-i", str(audio_file),
        "-vf", vf, "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "320k", "-ar", "44100",
        "-t", f"{DUR:.3f}", "-shortest", "-pix_fmt", "yuv420p", str(output_file)
    ]
    r = subprocess.run(mux_cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"[render] Final mux failed:\n{r.stderr.decode('utf-8', 'replace')[-800:]}")

    print(f"[render] [OK] Successfully rendered master film to {output_file}")
    return output_file

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Deterministic beat-locked film compiler")
    parser.add_argument("song_dir", nargs="?", default=r"X:\chloeos-maestro\songs\silicon_heartbeat", help="Song root directory")
    parser.add_argument("--shotlist", default=None, help="Custom shotlist.json path")
    parser.add_argument("--output", default=None, help="Custom output video path")
    parser.add_argument("--work-dir", default=None, help="Custom render_work directory")
    args = parser.parse_args()

    s_dir = Path(args.song_dir)
    out_f = Path(args.output) if args.output else None
    shot_f = Path(args.shotlist) if args.shotlist else None
    work_d = Path(args.work_dir) if args.work_dir else None

    render_film(s_dir, output_file=out_f, shotlist_file=shot_f, work_dir=work_d)
