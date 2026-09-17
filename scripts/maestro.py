#!/usr/bin/env python3
"""ChloeOS Maestro — The Master Music & Lyric Cinema Engine.

Orchestrates the complete 5-stage pipeline for any song in the library:
1. Music & Rhythmic Vector Analysis (Librosa, AudioFlux)
2. Variable-Duration Montage Blueprint Generation
3. LLM Lyric Direction & Visual Prompt Crafting (with Chloe & Rabbit consistency)
4. Targeted AI Video Generation (Agnes Video V2.0 API)
5. Drift-Free Beat-Locked Film Compilation (FFmpeg xfade chain, 180.000s @ 24fps)

Usage:
    python maestro.py --track songs/silicon_heartbeat [--render-only] [--generate-clips] [--max-clips 3]
    python maestro.py --all
"""

import argparse
import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable

def run_pipeline(song_dir: Path, generate_anchors: bool = False, max_anchors: int = 0,
                 generate_clips: bool = False, max_clips: int = 0, render_only: bool = False):
    song_dir = Path(song_dir).resolve()
    print(f"\n=======================================================")
    print(f"   CHLOEOS MAESTRO: {song_dir.name.upper()}")
    print(f"=======================================================\n")

    audio_file = next(song_dir.glob("*.wav"), None) or next(song_dir.glob("*.webm"), None)
    if not audio_file:
        sys.exit(f"Error: No audio file found in {song_dir}")

    scripts_dir = Path(__file__).parent

    # Stage 1: Music Analysis
    music_json = song_dir / f"{song_dir.name}.music.json"
    if not music_json.exists():
        print(f"[Stage 1/6] Analyzing acoustic vectors & beat grid...")
        subprocess.run([PYTHON, str(scripts_dir / "music_analyzer.py"),
                        str(audio_file), str(music_json), song_dir.name], check=True)
    else:
        print(f"[Stage 1/6] Music grid already analyzed: {music_json.name}")

    # Stage 2: Montage Blueprint
    blueprint_json = song_dir / "blueprint.json"
    if not blueprint_json.exists():
        print(f"[Stage 2/6] Generating variable-duration montage blueprint...")
        subprocess.run([PYTHON, str(scripts_dir / "montage_orchestrator.py"), str(song_dir)], check=True)
    else:
        print(f"[Stage 2/6] Montage blueprint already present.")

    # Stage 3: Lyric Direction
    shotlist_json = song_dir / "shotlist.json"
    if not shotlist_json.exists():
        print(f"[Stage 3/6] Directing lyrics & generating character-anchored prompts...")
        subprocess.run([PYTHON, str(scripts_dir / "lyric_director.py"), str(song_dir)], check=True)
    else:
        print(f"[Stage 3/6] Shotlist with visual prompts already present.")

    # Stage 4: Visual Anchor Generation via Google Imagen 3 (Optional / On-Demand)
    if generate_anchors:
        print(f"[Stage 4/6] Generating photorealistic visual anchors via Google Imagen 3...")
        cmd = [PYTHON, str(scripts_dir / "google_image_generator.py"), "--shotlist", str(shotlist_json)]
        if max_anchors > 0:
            cmd += ["--max", str(max_anchors)]
        subprocess.run(cmd, check=True)
    else:
        print(f"[Stage 4/6] Anchor generation skipped (use --generate-anchors to create Imagen 3 stills).")

    # Stage 5: Video Clip Generation (Optional / On-Demand)
    if generate_clips:
        print(f"[Stage 5/6] Generating AI clips via Agnes Video V2.0...")
        cmd = [PYTHON, str(scripts_dir / "agnes_video_batch_client.py"), "--shotlist", str(shotlist_json)]
        if max_clips > 0:
            cmd += ["--max", str(max_clips)]
        subprocess.run(cmd, check=True)
    else:
        print(f"[Stage 5/6] Video generation skipped (use --generate-clips to run video API).")

    # Stage 6: Final Render
    print(f"[Stage 6/6] Compiling beat-locked master film (180.000s @ 24fps)...")
    subprocess.run([PYTHON, str(scripts_dir / "render_final.py"), str(song_dir)], check=True)

    print(f"\n[OK] MAESTRO PIPELINE COMPLETE FOR {song_dir.name.upper()}!")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--track", default=r"X:\chloeos-maestro\songs\silicon_heartbeat",
                    help="Path to song directory")
    ap.add_argument("--generate-anchors", action="store_true",
                    help="Invoke Google Imagen 3 to generate visual anchor plates")
    ap.add_argument("--max-anchors", type=int, default=0,
                    help="Max anchor plates to generate (0 = all)")
    ap.add_argument("--generate-clips", action="store_true",
                    help="Invoke Agnes Video V2.0 API to generate clips")
    ap.add_argument("--max-clips", type=int, default=0,
                    help="Max clips to generate in this run (0 = all)")
    ap.add_argument("--all", action="store_true",
                    help="Process all songs under songs/ directory")
    args = ap.parse_args()

    if args.all:
        songs_dir = Path(r"X:\chloeos-maestro\songs")
        for s in songs_dir.iterdir():
            if s.is_dir():
                run_pipeline(
                    s,
                    generate_anchors=args.generate_anchors,
                    max_anchors=args.max_anchors,
                    generate_clips=args.generate_clips,
                    max_clips=args.max_clips,
                )
    else:
        run_pipeline(
            Path(args.track),
            generate_anchors=args.generate_anchors,
            max_anchors=args.max_anchors,
            generate_clips=args.generate_clips,
            max_clips=args.max_clips,
        )

if __name__ == "__main__":
    main()
