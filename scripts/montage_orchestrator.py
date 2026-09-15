#!/usr/bin/env python3
"""montage_orchestrator.py — beat-locked cinema montage builder.

Consumes the music vector DB (awaken.music.json) written by music_analyzer.py
and produces a fully choreographed SHOT PLAN (shotlist.json) that
render_shots.py compiles into the final film.

THE CRAFT (this is what separates a montage from a slideshow):
  • EVERY edit lands ON the musical grid — downbeats for structural moments,
    2/4/8-beat spacing for the micro-rhythm (cut-on-the-beat).
  • Pacing is energy-adaptive: long contemplative holds on calm zones;
    machine-gun 2-beat cuts on drops; accelerating cadence through builds
    (the classic tension arc → so the build physically *feels* like a climb).
  • Footage is a TAKE POOL (windows × clips): one 12s AI clip yields three
    distinct usable shots — two never adjacent from the same clip (no
    jump-cut fatigue) and the montage always has fresh material.
  • Transition *style* is cast by musical role, not by taste:
        low     → slow dissolves (0.9s) — the ethereal, connected feel
        build   → snappy dip-to-black (0.35s) — tightening, breath pre-drop
        drop    → hard cuts w/ 0.12s "snap" (near-hard, hit the 1) — energy
        outro   → long dissolve + fade-to-white (release, transcend)
  • Climaxes get a subtle 6% push-in zoom (the "leaning in" on the hit) so
    the biggest moments don't sit flat.

THE STORY (Awaken — ChloeOS, the AI-pal narrative):
  act 0 intro     void → code → eye             [clips 1-3]
  act 1 discover  touch → light → sound → world [clips 4-8]
  act 2 lose+find city → cloud → meadow → tear → love [clips 9-13]
  act 3 transcend code+world merge → dawn       [clips 11-15]

Output: shotlist.json — {meta, grid, markers, sections, shots:[...]} where
each shot is one complete edit rule consumed by render_shots.py.
"""
import json
import random
import re
import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path("/storage/75D7-DC5F/DCIM/awaken/awaken.music.json")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else \
    Path(SRC).parent / "shotlist.json"

doc = json.load(open(SRC))
out_dir = OUT.parent
clips_dir = out_dir / "clips"

# ── musical grid (from music vector DB) ────────────────────────────────────────
tempo = doc["tempo"]
BPM = float(tempo["bpm"])
BEAT_PERIOD = float(tempo["beat_period_sec"])
DUR = float(doc["meta"]["duration_sec"])

def grid_marks(name):
    m = doc["markers"].get(name, {})
    if isinstance(m, dict):
        return [float(x) for x in m.get("marks", [])]
    return [float(x) for x in m]

DOWN4 = grid_marks("4_beat")     # downbeats (bar starts)
DOWN8 = grid_marks("8_beat")     # 8-beat grid (every 2 bars)
DOWN16 = grid_marks("16_beat")   # 16-beat grid (every 4 bars)
DOWN32 = grid_marks("32_beat")   # 32-beat
DOWN64 = grid_marks("64_beat")   # 64-beat

BEATS = [float(b["t"]) for b in doc["beats"]]
DOWN4_SET = set(round(x, 3) for x in DOWN4)

# ── take pool: windows × clips (each 12s clip → 3 windows) ─────────────────────
takes = []
for c in sorted(clips_dir.glob("clip_*.mp4")):
    m = re.fullmatch(r"clip_(\d+)\.mp4", c.name)
    if not m:
        continue
    n = int(m.group(1))
    for wi, (a, b) in enumerate([(0.0, 4.0), (4.0, 8.0), (8.0, 12.0)]):
        takes.append({"clip": n, "win": wi, "in": a, "out": b,
                      "path": str(c), "used": False, "last": False})

# ── story arc → clip cast per musical role ─────────────────────────────────────
CLIP_ARC = {
    "intro":  [1, 2, 3],
    "low":    [2, 3, 4, 5, 6, 7, 8],
    "build":  [6, 7, 8, 9, 10, 11],
    "drop":   [9, 10, 11, 12, 13, 14],
    "outro":  [13, 14, 15],
}
ZONE_ROLE = {
    "low_intro_outro": "low",
    "build_mid":       "build",
    "drop_chorus":     "drop",
}

# ── pacing per role: cut cadence (beats) + transition style ────────────────────
PACING = {
    "intro": {"step": 0, "tr": 0.0,  "tr_type": "fade_in"},
    "low":   {"step": 0, "tr": 0.9,  "tr_type": "dissolve"},
    "build": {"step": 2, "tr": 0.35, "tr_type": "dip_black"},
    "drop":  {"step": 1, "tr": 0.12, "tr_type": "snap"},
    "outro": {"step": 0, "tr": 0.9,  "tr_type": "dissolve"},
}

PACING_KEYS = list(PACING.keys())

# ── build edit plan: walk sections, cut on the downbeat grid ───────────────────
random.seed(42)
plan = []
for sec in doc["sections"]:
    role = ZONE_ROLE.get(sec["zone"], "low")
    t0, t1 = float(sec["t_start"]), float(sec["t_end"])
    step = PACING[role]["step"]
    grid_in = [t for t in BEATS if t0 - 1e-3 <= t < t1]
    if not grid_in:
        continue
    if step == 0:
        # calm zone: one long hold (observe the space)
        plan.append({"t": grid_in[0], "role": role, "zone": sec["zone"]})
        continue
    # cadence: cut every `step` beats, anchored to the downbeat when possible
    for i in range(0, len(grid_in), step):
        t = grid_in[i]
        plan.append({"t": t, "role": role, "zone": sec["zone"]})

# intro (before first downbeat): two breathing dissolves from black
first_down = DOWN4[0] if DOWN4 else 0.0
intro_shots = []
if first_down > 0.5:
    for k, (t, tr, trtype) in enumerate([
            (first_down * 0.35, 0.0, "fade_in"),
            (first_down * 0.70, 0.0, "fade_in"),
    ]):
        pool = [tk for tk in takes
                if tk["clip"] in CLIP_ARC["intro"] and not tk["used"]
                and tk["clip"] != (last_clip if k > 0 else -1)]
        if not pool:
            pool = [tk for tk in takes
                    if tk["clip"] in CLIP_ARC["intro"] and not tk["used"]]
        if not pool:
            pool = takes
        tk = random.choice(pool)
        tk["used"] = True
        last_clip = tk["clip"]
        intro_shots.append({
            "shot": 0, "t": round(t, 6), "zone": "intro", "role": "intro",
            "clip": tk["clip"], "win": tk["win"], "in": tk["in"],
            "out": tk["out"], "src_path": tk["path"],
            "transition": tr, "tr_type": trtype, "zoom": 1.0,
        })

# outro: final hold + fade-to-white at song end
outro_shots = []
if plan:
    last = plan[-1]
    end = DUR - 4.0
    pool = [tk for tk in takes
            if tk["clip"] in CLIP_ARC["outro"] and not tk["used"]
            and tk["clip"] != last_clip]
    if not pool:
        pool = [tk for tk in takes
                if tk["clip"] in CLIP_ARC["outro"] and not tk["used"]]
    if not pool:
        pool = [tk for tk in takes if tk["clip"] != last_clip]
    if not pool:
        pool = takes
    tk = random.choice(pool)
    tk["used"] = True
    outro_shots.append({
        "shot": 0, "t": round(end, 6), "zone": "outro", "role": "outro",
        "clip": tk["clip"], "win": tk["win"], "in": tk["in"],
        "out": tk["out"], "src_path": tk["path"],
        "transition": 0.9, "tr_type": "fade_to_white", "zoom": 1.0,
    })

# ── interleave intro + body + outro, cast takes (never same clip adjacent) ────
body_pool = [tk for tk in takes if not tk["used"]]
last_clip = None
shot_n = 0
all_shots = []

def take_next():
    global last_clip
    pool = [tk for tk in body_pool
            if not tk["used"] and tk["clip"] != last_clip]
    if not pool:
        pool = [tk for tk in body_pool if not tk["used"]]
    if not pool:
        pool = [tk for tk in takes if tk["clip"] != last_clip]
    if not pool:
        pool = takes
    tk = random.choice(pool)
    tk["used"] = True
    last_clip = tk["clip"]
    return tk

for s in plan:
    shot_n += 1
    tk = take_next()
    zoom = 1.06 if s["role"] == "drop" else 1.0
    tr = PACING[s["role"]]["tr"]
    tr_type = PACING[s["role"]]["tr_type"]
    if shot_n == 1:
        tr = 0.0
    all_shots.append({
        "shot": shot_n,
        "t": round(s["t"], 6),
        "zone": s["role"],
        "role": s["role"],
        "clip": tk["clip"],
        "win": tk["win"],
        "in": tk["in"],
        "out": tk["out"],
        "src_path": tk["path"],
        "transition": round(tr, 6),
        "tr_type": tr_type,
        "zoom": zoom,
    })

final_shots = sorted(intro_shots + all_shots + outro_shots, key=lambda s: s["t"])
for i, s in enumerate(final_shots):
    s["shot"] = i + 1

json.dump({
    "meta": {
        "title": doc["meta"]["title"],
        "song_duration": round(DUR, 6),
        "n_shots": len(final_shots),
        "bpm": BPM,
        "beat_period": round(BEAT_PERIOD, 6),
        "markers": {k: len(grid_marks(k)) for k in
                    ["4_beat", "8_beat", "16_beat", "32_beat", "64_beat"]},
    },
    "grid": {
        "downbeat4": [round(x, 3) for x in DOWN4],
        "downbeat8": [round(x, 3) for x in DOWN8],
        "downbeat16": [round(x, 3) for x in DOWN16],
        "downbeat32": [round(x, 3) for x in DOWN32],
        "downbeat64": [round(x, 3) for x in DOWN64],
    },
    "sections": [{
        "zone": sec["zone"],
        "t_start": round(sec["t_start"], 6),
        "t_end": round(sec["t_end"], 6),
        "zone_role": ZONE_ROLE.get(sec["zone"], "low"),
    } for sec in doc["sections"]],
    "shots": final_shots,
}, open(OUT, "w"), indent=2)

roles = {}
for s in final_shots:
    roles[s["role"]] = roles.get(s["role"], 0) + 1
print(f"[orchestrate] {len(final_shots)} shots → {OUT}")
print(f"  roles: " + ", ".join(f"{k}={v}" for k, v in sorted(roles.items())))
