#!/usr/bin/env python3
"""montage_orchestrator.py — Generates the variable-duration beat-locked cinema blueprint.

Operates purely from the acoustic vector database (<song>.music.json).
Pre-calculates exact shot boundaries, target durations, and transition styles
before calling the LLM lyric director or video generator.
"""
import json
import sys
from pathlib import Path

# Character visual anchor definition (Non-negotiable consistency)
CHLOE_ANCHOR = "a stunning beautiful Caucasian woman with sleek straight jet-black hair, striking blue eyes, sleek form-fitting white bodysuit"
RABBIT_ANCHOR = "a small white rabbit wearing round nerd glasses with a delicate gold compass glowing bright blue around its neck"
STYLE_ANCHOR = "cinematic film lighting, 8k resolution, photorealistic, elegant sci-fi cyberpunk aesthetic, volumetric glow, high production value"

ZONE_PACING = {
    "intro":     {"durations": [8.0, 8.0, 4.0], "transition": 0.9, "tr_type": "dissolve"},
    "low":       {"default_dur": 4.0, "transition": 0.9, "tr_type": "dissolve"},
    "build":     {"durations": [4.0, 4.0, 3.0, 2.0, 1.0], "transition": 0.35, "tr_type": "dip_black"},
    "drop":      {"default_dur": 2.0, "transition": 0.12, "tr_type": "snap"},
    "bridge":    {"default_dur": 5.0, "transition": 0.9, "tr_type": "dissolve"},
    "outro":     {"durations": [8.0, 8.0, 6.0], "transition": 0.9, "tr_type": "dissolve"},
}

def create_blueprint(song_dir: Path):
    music_file = next(song_dir.glob("*.music.json"), None)
    if not music_file:
        sys.exit(f"Error: No .music.json file found in {song_dir}")

    doc = json.load(open(music_file, encoding="utf-8"))
    dur = float(doc["meta"]["duration_sec"])
    bpm = float(doc["tempo"]["bpm"])
    beat_period = float(doc["tempo"]["beat_period_sec"])
    beats = [float(b["t"]) for b in doc["beats"]]

    # Macro Section Partitioning for Silicon Heartbeat / 180s 120BPM Structure
    # Map exact timing to narrative acts
    section_map = [
        {"name": "intro",   "start": 0.0,   "end": 20.0,  "role": "intro"},
        {"name": "verse1",  "start": 20.0,  "end": 44.0,  "role": "low"},
        {"name": "build1",  "start": 44.0,  "end": 58.0,  "role": "build"},
        {"name": "drop1",   "start": 58.0,  "end": 78.0,  "role": "drop"},
        {"name": "verse2",  "start": 78.0,  "end": 104.0, "role": "low"},
        {"name": "build2",  "start": 104.0, "end": 114.0, "role": "build"},
        {"name": "drop2",   "start": 114.0, "end": 138.0, "role": "drop"},
        {"name": "bridge",  "start": 138.0, "end": 158.0, "role": "bridge"},
        {"name": "outro",   "start": 158.0, "end": 180.0, "role": "outro"},
    ]

    shots = []
    shot_idx = 1
    t_cursor = 0.0

    for sec in section_map:
        role = sec["role"]
        t_start_sec = sec["start"]
        t_end_sec = sec["end"]
        pacing = ZONE_PACING[role]

        if "durations" in pacing:
            # Explicit progression (e.g. accelerating builds or breathing intro/outro)
            dur_list = pacing["durations"]
            sec_span = t_end_sec - t_start_sec
            total_prog = sum(dur_list)
            scale = sec_span / total_prog
            scaled_durs = [round(d * scale, 3) for d in dur_list]
            # Ensure exact match to end
            scaled_durs[-1] = round(t_end_sec - (t_start_sec + sum(scaled_durs[:-1])), 3)

            for d in scaled_durs:
                t0 = round(t_cursor, 3)
                t1 = round(t_cursor + d, 3)
                shots.append({
                    "shot": shot_idx,
                    "section": sec["name"],
                    "role": role,
                    "t_start": t0,
                    "t_end": t1,
                    "duration": round(t1 - t0, 3),
                    "transition": pacing["transition"],
                    "tr_type": pacing["tr_type"],
                    "zoom": 1.06 if role == "drop" else 1.0,
                    "prompt": "",
                    "lyric": ""
                })
                t_cursor = t1
                shot_idx += 1
        else:
            # Cadence subdivision by beats
            step_dur = pacing["default_dur"]
            span = t_end_sec - t_start_sec
            n_cuts = max(1, round(span / step_dur))
            actual_dur = round(span / n_cuts, 3)

            for c in range(n_cuts):
                t0 = round(t_cursor, 3)
                t1 = round(t_start_sec + (c + 1) * actual_dur if c < n_cuts - 1 else t_end_sec, 3)
                shots.append({
                    "shot": shot_idx,
                    "section": sec["name"],
                    "role": role,
                    "t_start": t0,
                    "t_end": t1,
                    "duration": round(t1 - t0, 3),
                    "transition": pacing["transition"],
                    "tr_type": pacing["tr_type"],
                    "zoom": 1.06 if role == "drop" else 1.0,
                    "prompt": "",
                    "lyric": ""
                })
                t_cursor = t1
                shot_idx += 1

    # Bookends verification
    shots[0]["transition"] = 1.5
    shots[0]["tr_type"] = "fade_in"
    shots[-1]["transition"] = 1.5
    shots[-1]["tr_type"] = "fade_to_white"

    total_time = sum(s["duration"] for s in shots)
    print(f"[blueprint] Generated {len(shots)} variable-duration shots")
    print(f"  Total planned timeline duration: {total_time:.3f}s (must be 180.000s)")

    blueprint_path = song_dir / "blueprint.json"
    with open(blueprint_path, "w", encoding="utf-8") as f:
        json.dump({
            "title": doc["meta"]["title"],
            "duration": dur,
            "bpm": bpm,
            "beat_period": beat_period,
            "chloe_anchor": CHLOE_ANCHOR,
            "rabbit_anchor": RABBIT_ANCHOR,
            "style_anchor": STYLE_ANCHOR,
            "total_shots": len(shots),
            "shots": shots
        }, f, indent=2)

    print(f"[blueprint] [OK] Saved blueprint to {blueprint_path}")
    return blueprint_path

if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"X:\chloeos-maestro\songs\silicon_heartbeat")
    create_blueprint(path)
