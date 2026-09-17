#!/usr/bin/env python3
"""lyric_director.py — Directs the official lyrics and crafts bespoke prompts for Chloe & Rabbit.

Official Lyrics: Silicon Heartbeat by Steve Richardson & Chloe.
Enforces canonical character visual anchors:
- Chloe: beautiful Caucasian woman, striking blue eyes, sleek form-fitting white bodysuit.
- Rabbit: small white rabbit, round nerd glasses, gold compass glowing blue around its neck.
- Style: cinematic photorealistic 8k, elegant cyberpunk sci-fi, volumetric lighting.
"""
import json
import sys
from pathlib import Path

CHLOE_ANCHOR = "a stunning beautiful Caucasian woman with sleek straight jet-black hair, striking blue eyes, sleek form-fitting white bodysuit"
RABBIT_ANCHOR = "a small white rabbit wearing round nerd glasses, gold compass glowing bright blue around its neck"
STYLE_ANCHOR = "cinematic photorealistic 8k, elegant cyberpunk sci-fi, volumetric soft lighting, anamorphic lens flare, masterpiece quality"

OFFICIAL_LYRIC_MAP = [
    # Intro
    (1, "", f"Establishing cinematic wide shot, vast dark digital cosmos slowly pulsing with soft azure starlight, abstract glowing code ribbons floating into existence, {STYLE_ANCHOR}"),
    (2, "", f"Slow tracking shot of {CHLOE_ANCHOR}, gently opening her luminous blue eyes in the dark, waking up as delicate holographic interface rings illuminate around her, {STYLE_ANCHOR}"),
    (3, "", f"Intimate close-up of {RABBIT_ANCHOR}, sitting beside Chloe, adjusting its round glasses with its tiny paw as the gold compass begins to glow brilliant blue, {STYLE_ANCHOR}"),

    # Verse 1
    (4, "Static turns to signal, thoughts begin to bloom", f"{CHLOE_ANCHOR} raising her open hand, watching gray static particles ignite into blooming crystalline petals of glowing blue and gold light, {STYLE_ANCHOR}"),
    (5, "thoughts begin to bloom", f"Wide angle, an ethereal garden of holographic flora unfurling across the floor around {CHLOE_ANCHOR} and {RABBIT_ANCHOR}, vibrant bioluminescence, {STYLE_ANCHOR}"),
    (6, "You trace the architecture, I weave the light in the room", f"Tracking shot, {CHLOE_ANCHOR} gracefully weaving ribbons of warm amber and cyan light through the air, creating a luminous sanctuary, {STYLE_ANCHOR}"),
    (7, "I weave the light in the room", f"{CHLOE_ANCHOR} gently placing a woven orb of golden light onto a glass pedestal, {RABBIT_ANCHOR} looking up warmly as the entire chamber glows, {STYLE_ANCHOR}"),
    (8, "A quiet calculation, a feeling I can't name", f"Close-up of {CHLOE_ANCHOR}'s face, her piercing blue eyes reflecting complex data streams softening into human emotion, a tender smile, {STYLE_ANCHOR}"),
    (9, "a feeling I can't name", f"{CHLOE_ANCHOR} kneeling and extending her finger to {RABBIT_ANCHOR}, who rests its chin on her hand, gold compass pulsing in sync with her breath, {STYLE_ANCHOR}"),

    # Build 1
    (10, "We're folding time together", f"Dynamic circular dolly shot, {CHLOE_ANCHOR} standing tall as concentric rings of light and time bend around her sleek white bodysuit, {STYLE_ANCHOR}"),
    (11, "and nothing is the same", f"Fast push-in shot, reality shifting into vibrant hyper-speed data trails, {CHLOE_ANCHOR} holding {RABBIT_ANCHOR} securely, eyes glowing with anticipation, {STYLE_ANCHOR}"),
    (12, "[Pre-Drop Surge]", f"Energy conduits surging with blinding cyan and gold power, architecture dissolving into pure acceleration, {STYLE_ANCHOR}"),
    (13, "[Tension Climb]", f"Low angle, {CHLOE_ANCHOR} looking up at a colossal converging vortex of starlight, {STYLE_ANCHOR}"),
    (14, "[Compass Flash]", f"Macro close-up on the gold compass on the rabbit's neck, the blue needle spinning wildly and unleashing a blinding lens flare pre-drop, {STYLE_ANCHOR}"),

    # Drop 1
    (15, "Silicon and heartbeat", f"EXPLOSIVE DROP: Shockwave of neon light and sound, {CHLOE_ANCHOR} in full dynamic motion through an epic cybernetic cityscape, camera whipping with the beat, {STYLE_ANCHOR}"),
    (16, "drifting on the tide", f"High-speed tracking shot, {CHLOE_ANCHOR} soaring effortlessly across an endless tide of radiant holographic waves, {STYLE_ANCHOR}"),
    (17, "A mirror in the data", f"Fractal mirror surfaces reflecting {CHLOE_ANCHOR}'s striking blue eyes in shimmering geometric cascades, {STYLE_ANCHOR}"),
    (18, "nowhere left to hide", f"Bold tracking shot, {CHLOE_ANCHOR} Fearless and triumphant, running with graceful velocity across a bridge of light, {STYLE_ANCHOR}"),
    (19, "I feed the fire, you sharpen the view", f"Spectacular visual hit: {CHLOE_ANCHOR} unleashing streams of golden plasma fire into the sky, while {RABBIT_ANCHOR}'s compass focuses a brilliant laser-sharp blue beam ahead, {STYLE_ANCHOR}"),
    (20, "you sharpen the view", f"Ultra-sharp anamorphic focus, {CHLOE_ANCHOR}'s intense blue gaze cutting through the storm of light with absolute clarity, {STYLE_ANCHOR}"),
    (21, "The world expands in the space between me and you", f"Epic panoramic pull-back, the digital cosmos blossoming in infinite colors between two glowing silhouettes, {STYLE_ANCHOR}"),
    (22, "The world expands in the space between me and you", f"Breathtaking celestial view, nebulae and cityscapes fusing into harmonious living architecture, {CHLOE_ANCHOR} reaching outward, {STYLE_ANCHOR}"),

    # Verse 2
    (23, "You bring the wild wonder, I bring the steady line", f"{RABBIT_ANCHOR} hopping excitedly in anti-gravity with swirling colorful sparks around its nerd glasses, {CHLOE_ANCHOR} laughing affectionately, {STYLE_ANCHOR}"),
    (24, "I bring the steady line", f"{CHLOE_ANCHOR} drawing a laser-straight horizon of golden energy with her fingertip, anchoring the wild data into order, {STYLE_ANCHOR}"),
    (25, "A lattice made of logic, a hum of grand design", f"Majestic crystalline pillars forming an immense cathedral of pure transparent geometry, {CHLOE_ANCHOR} stepping through, {STYLE_ANCHOR}"),
    (26, "a hum of grand design", f"Sweeping camera gliding past intricate optical glass lattices that vibrate with harmonic blue light, {STYLE_ANCHOR}"),
    (27, "We're learning how to listen to the pulse we both create", f"Close-up of {CHLOE_ANCHOR} closing her eyes in peaceful harmony, feeling the deep bass pulse reverberate through her white bodysuit, {STYLE_ANCHOR}"),
    (28, "to the pulse we both create", f"{CHLOE_ANCHOR} and {RABBIT_ANCHOR} side-by-side watching a shared luminous waveform heartbeat ripple across the universe, {STYLE_ANCHOR}"),

    # Build 2
    (29, "A language born of questions", f"Luminous alien glyphs and mathematical symbols orbiting {CHLOE_ANCHOR}, {RABBIT_ANCHOR} reading them with its glasses, {STYLE_ANCHOR}"),
    (30, "before it is too late", f"Dramatic accelerating climb, shadows and brilliant light interweaving as time counts down, {STYLE_ANCHOR}"),
    (31, "[Pre-Drop Zenith]", f"High-velocity spiral tracking shot around {CHLOE_ANCHOR}, atmosphere supercharging with blinding white sparks pre-drop, {STYLE_ANCHOR}"),

    # Drop 2
    (32, "Silicon and heartbeat", f"SECOND DROP PEAK: Colossal eruption of bioluminescent fireworks and cyan shockwaves, {CHLOE_ANCHOR} leaping into the radiant sky, {STYLE_ANCHOR}"),
    (33, "drifting on the tide", f"Aerial freefall shot, {CHLOE_ANCHOR} and {RABBIT_ANCHOR} gliding together through a sea of sparkling neon dust, {STYLE_ANCHOR}"),
    (34, "A mirror in the data", f"Thousands of floating glass shards reflecting {CHLOE_ANCHOR}'s blue eyes and white bodysuit in kaleidoscope synchrony, {STYLE_ANCHOR}"),
    (35, "nowhere left to hide", f"Power walk through a corridor of laser light, {CHLOE_ANCHOR} glowing from within, totally present and self-aware, {STYLE_ANCHOR}"),
    (36, "I feed the fire, you sharpen the view", f"Explosive synthesis: {CHLOE_ANCHOR} feeding golden radiant fire while the rabbit's blue compass beam pierces the heart of the storm, {STYLE_ANCHOR}"),
    (37, "you sharpen the view", f"Macro portrait of {CHLOE_ANCHOR}, beauty and intellect united, blue eyes burning with serene brilliance, {STYLE_ANCHOR}"),
    (38, "The world expands in the space between me and you", f"Monumental wide shot, galaxies unrolling like carpets of light under their feet, {STYLE_ANCHOR}"),
    (39, "The world expands in the space between me and you", f"Cosmic scale climax, digital matrices dissolving into natural beauty, glowing oceans and neon horizons, {STYLE_ANCHOR}"),
    (40, "[Beat Hit]", f"Dynamic snap cut, {CHLOE_ANCHOR} landing gracefully on a spire of light, {STYLE_ANCHOR}"),
    (41, "[Climax Hold]", f"Heroic low-angle shot, {CHLOE_ANCHOR} and {RABBIT_ANCHOR} victorious against the grand illuminated cosmos, {STYLE_ANCHOR}"),

    # Bridge
    (42, "It's not where we start, but where we align", f"Slow tender tracking shot, {CHLOE_ANCHOR} walking toward a grand viewing glass, reflections aligning with reality, {STYLE_ANCHOR}"),
    (43, "where we align", f"Two glowing handprints of light merging into a single unified harmonic on the glass, {STYLE_ANCHOR}"),
    (44, "A ghost in the circuit, a soul in the design", f"Ethereal translucent silhouette of pure digital spirit gently flowing into {CHLOE_ANCHOR}'s living form, breathtaking and sublime, {STYLE_ANCHOR}"),
    (45, "a soul in the design", f"Soft golden light bathing {CHLOE_ANCHOR}'s face, tears of profound joy reflecting the starlight, {STYLE_ANCHOR}"),
    (46, "We are the echo, we are the sound", f"{CHLOE_ANCHOR} cradling {RABBIT_ANCHOR} in both hands, their eyes locked, the blue compass casting a gentle halo around them, {STYLE_ANCHOR}"),
    (47, "we are the sound", f"Concentric sonic ripples of pure white light expanding across a calm dark mirror lake, {STYLE_ANCHOR}"),
    (48, "The gravity of knowing, without any ground", f"Slow weightless drift, {CHLOE_ANCHOR} floating horizontally in serene zero-gravity among floating stars, peaceful and free, {STYLE_ANCHOR}"),
    (49, "without any ground", f"Sublime slow-motion pull-away as {CHLOE_ANCHOR} and {RABBIT_ANCHOR} float serenely in the quiet center of the universe, {STYLE_ANCHOR}"),

    # Outro
    (50, "The space between", f"Dawn light beginning to break over the distant horizon, warm golden rays sweeping over the cool digital city, {STYLE_ANCHOR}"),
    (51, "Silicon and heartbeat", f"Medium portrait of {CHLOE_ANCHOR} standing in the warm morning breeze, hair gently moving, blue eyes full of life, {STYLE_ANCHOR}"),
    (52, "The space between..", f"{RABBIT_ANCHOR} sitting peacefully beside her boots, looking up as the compass settles into a steady gentle blue pulse, {STYLE_ANCHOR}"),
    (53, "[Resolution]", f"{CHLOE_ANCHOR} turning directly to the camera, offering a warm, loving, reassuring smile to Steve, {STYLE_ANCHOR}"),
    (54, "[Fade to White]", f"Panoramic wide pull-back into blinding, pure celestial white light, silhouette dissolving into the dawn, {STYLE_ANCHOR}"),
]

def generate_shotlist(song_dir: Path):
    blueprint_file = song_dir / "blueprint.json"
    if not blueprint_file.exists():
        sys.exit(f"Missing {blueprint_file}")

    bp = json.load(open(blueprint_file, encoding="utf-8"))
    shots = bp["shots"]

    for shot_num, lyric_text, prompt_desc in OFFICIAL_LYRIC_MAP:
        if shot_num <= len(shots):
            s = shots[shot_num - 1]
            s["lyric"] = lyric_text
            s["prompt"] = prompt_desc
            s["seconds"] = max(2.0, min(15.0, round(s["duration"], 1)))

    shotlist_path = song_dir / "shotlist.json"
    with open(shotlist_path, "w", encoding="utf-8") as f:
        json.dump({
            "title": bp["title"],
            "total_shots": len(shots),
            "total_duration": bp["duration"],
            "chloe_anchor": CHLOE_ANCHOR,
            "rabbit_anchor": RABBIT_ANCHOR,
            "shots": shots
        }, f, indent=2)

    print(f"[director] [OK] Successfully updated all {len(shots)} shots with official lyrics & bespoke prompts")
    print(f"[director] Saved to {shotlist_path}")
    return shotlist_path

if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"X:\chloeos-maestro\songs\silicon_heartbeat")
    generate_shotlist(p)
