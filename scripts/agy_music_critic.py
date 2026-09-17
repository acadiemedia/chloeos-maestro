#!/usr/bin/env python3
"""Google Antigravity CLI (agy) Music Critic & Analyzer.

Invokes the Google Antigravity CLI (agy) to ingest acoustic vectors, lyrics,
and tempo structure, producing an in-depth creative critique and cinematic
opinion saved as `music_opinion.json`.

Usage:
    python agy_music_critic.py songs/silicon_heartbeat [--agy-bin agy]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# ── Prompt Template for AGY ───────────────────────────────────────────────────

CRITIC_SYSTEM_PROMPT = """You are the Senior Music & Cinematic Director for ChloeOS Maestro.
Your mission is to perform a deep artistic, emotional, and structural analysis of a music track
using its acoustic analysis and lyrics, then output your expert opinion as a clean JSON object.

The music video will star:
- Chloe: stunning beautiful Caucasian woman, sleek raven jet-black hair, striking blue eyes, tailored white tactical suit.
- Companion: cute small white rabbit with round nerd glasses and a glowing cyan-gold compass.
- Cyber-interceptor vehicle: aerodynamic white speeder with cyan neon underglow.
- Aesthetic: Grounded Cyber-Noir (Blade Runner 2049, Tron: Legacy, 35mm film grain, wet asphalt, volumetric lighting).

Analyze the song and return a strictly valid JSON object with these keys:
{
  "song_title": "string",
  "overall_mood": "string summarizing dominant tone and emotional trajectory",
  "tempo_critique": "string evaluating tempo, beat grid, and sync opportunities",
  "narrative_theme": "string describing the overarching story arc",
  "character_emotional_journey": "string describing Chloe's psychological state across the track",
  "energy_sections": [
    {
      "section": "Intro | Verse 1 | Build-up | Drop 1 | Chorus | Bridge | Climax | Outro",
      "t_start": float,
      "t_end": float,
      "energy_level": "Low | Rising | Peak | Explosive | Calming",
      "cinematography": "Camera motion grammar (e.g. Extreme low-angle forward road tracker, High-speed side-scroller parallax)",
      "color_palette": "Primary and accent colors (e.g. Deep teal, wet asphalt black, sharp cyan neon)",
      "lighting_and_atmosphere": "e.g. Volumetric fog, rain streaking horizontally, lens flares",
      "narrative_action": "What happens dramatically in this section"
    }
  ],
  "visual_storyboard_directives": [
    "List of 5-8 concrete rules for the visual storyboard writer to follow"
  ],
  "director_summary": "Paragraph summarizing your vision for this film"
}

Output ONLY the JSON object. Do not wrap in markdown or explanation.
"""


def build_song_summary(song_dir: Path) -> dict:
    """Collect audio analysis, lyrics, and metadata into an analysis payload."""
    song_dir = Path(song_dir).resolve()
    
    # Check lyrics
    lyrics_file = song_dir / "lyrics_clean.json" or song_dir / "lyrics.txt"
    lyrics_data = []
    if lyrics_file.exists():
        try:
            lyrics_data = json.loads(lyrics_file.read_text(encoding="utf-8"))
        except Exception:
            lyrics_data = lyrics_file.read_text(encoding="utf-8")

    # Check music json
    music_file = next(song_dir.glob("*.music.json"), None)
    music_meta = {}
    if music_file and music_file.exists():
        try:
            m_raw = json.loads(music_file.read_text(encoding="utf-8"))
            music_meta = {
                "duration": m_raw.get("duration"),
                "bpm": m_raw.get("bpm"),
                "key": m_raw.get("key"),
                "energy_envelope": m_raw.get("energy_envelope", [])[:50]  # sample
            }
        except Exception:
            pass

    return {
        "song_name": song_dir.name,
        "music_metadata": music_meta,
        "lyrics_sample": lyrics_data[:20] if isinstance(lyrics_data, list) else lyrics_data[:1000],
    }


def call_agy_cli(prompt: str, agy_bin: str = "agy") -> str | None:
    """Execute the agy CLI tool non-interactively if available."""
    bin_path = shutil.which(agy_bin) or shutil.which("agy.cmd") or shutil.which("agy.exe")
    if not bin_path:
        return None

    try:
        proc = subprocess.run(
            [bin_path, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace"
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except Exception as e:
        print(f"[agy_music_critic] Warning: agy CLI call failed: {e}")

    return None


def call_gemini_api_fallback(prompt: str, api_key: str) -> str | None:
    """Call Google Gemini API as a fallback if agy CLI is headless/offline."""
    if not api_key:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[agy_music_critic] Warning: Gemini API fallback failed: {e}")
        return None


def generate_structured_critic_fallback(song_summary: dict) -> dict:
    """Deterministic high-quality fallback opinion if network is unreachable."""
    bpm = song_summary.get("music_metadata", {}).get("bpm", 120.0) or 120.0
    duration = song_summary.get("music_metadata", {}).get("duration", 180.0) or 180.0

    return {
        "song_title": song_summary.get("song_name", "Unknown Track"),
        "overall_mood": "High-velocity Cyber-Noir adrenaline with an undercurrent of emotional awakening and triumphant resolve.",
        "tempo_critique": f"Locked at {bpm:.1f} BPM ({240.0/bpm:.2f}s per 2-bar cycle). Strong rhythmic percussion demands forward kinetic camera tracking.",
        "narrative_theme": "A high-speed cybernetic odyssey across subterranean expressways, breaking through the digital firewall into dawn.",
        "character_emotional_journey": "Chloe begins in cold tactical focus, awakens to emotional resonance with her companion, and reaches fearless transcendence.",
        "energy_sections": [
            {
                "section": "Intro (Awakening)",
                "t_start": 0.0,
                "t_end": 20.0,
                "energy_level": "Low",
                "cinematography": "Forward push dolly through misty industrial hangar, headlights snapping on.",
                "color_palette": "Deep industrial charcoal, cyan headlights, cold concrete.",
                "lighting_and_atmosphere": "Volumetric mist, flickering overhead fluorescents.",
                "narrative_action": "System boot sequence. Vehicle thrusters prime as the compass needle locks coordinates."
            },
            {
                "section": "Verse 1 (Skyway Launch)",
                "t_start": 20.0,
                "t_end": 52.0,
                "energy_level": "Rising",
                "cinematography": "Extreme low-angle rear pursuit cam rushing out onto wet elevated highway.",
                "color_palette": "Rain-slick asphalt, magenta billboards, vibrant teal tire trails.",
                "lighting_and_atmosphere": "Heavy horizontal rain streaks, reflections on wet road.",
                "narrative_action": "Chloe accelerates the interceptor onto the skyway, weaving past automated drones."
            },
            {
                "section": "Build-up (Data Canyon)",
                "t_start": 52.0,
                "t_end": 80.0,
                "energy_level": "Peak",
                "cinematography": "High-speed side-scroller multi-layered parallax tracking left-to-right.",
                "color_palette": "Deep amber neon, electric blue warning pylons, dark obsidian towers.",
                "lighting_and_atmosphere": "Flashing tunnel strobe rings, atmospheric motion blur.",
                "narrative_action": "Descent into subterranean data gorge. Companion rabbit stabilizes the navigational compass."
            },
            {
                "section": "Drop 1 (Supersonic Breach)",
                "t_start": 80.0,
                "t_end": 120.0,
                "energy_level": "Explosive",
                "cinematography": "Low hood-cam rushing inches above the road at terminal velocity.",
                "color_palette": "Blinding cyan plasma flames, chrome highlights, streak flares.",
                "lighting_and_atmosphere": "Shockwave air distortion, intense anamorphic flare.",
                "narrative_action": "Twin plasma afterburners ignite, shattering the sound barrier."
            },
            {
                "section": "Bridge (Zero-Gravity Rift)",
                "t_start": 120.0,
                "t_end": 144.0,
                "energy_level": "Calming",
                "cinematography": "Slow majestic orbital pull-back, floating through atmospheric aurora.",
                "color_palette": "Soft celestial violet, azure starlight, delicate gold compass glow.",
                "lighting_and_atmosphere": "Weightless particles, gentle rim light on Chloe's profile.",
                "narrative_action": "Moment of stillness above the clouds. Chloe shares a determined glance with her companion."
            },
            {
                "section": "Climax & Outro (Celestial Dawn)",
                "t_start": 144.0,
                "t_end": duration,
                "energy_level": "Triumphant",
                "cinematography": "Sweeping lateral crane shot rising toward the horizon sun.",
                "color_palette": "Warm golden amber dawn breaking through dark teal haze.",
                "lighting_and_atmosphere": "Volumetric sunrise rays illuminating the horizon.",
                "narrative_action": "The interceptor emerges onto the infinite coast as a radiant sunrise breaks."
            }
        ],
        "visual_storyboard_directives": [
            "Strictly enforce Chloe's raven jet-black hair and blue eyes in all character shots.",
            "Use physical vehicles and real atmospheric textures (rain, asphalt, concrete, mist) rather than cheesy abstract holograms.",
            "Maintain continuous forward or lateral camera motion to honor the 120 BPM driving momentum.",
            "Keep shots between 6 and 10 seconds to allow audience immersion without visual whiplash.",
            "Isolate subjects: vehicle exterior, cockpit hero profile, and companion detail must be separate cuts."
        ],
        "director_summary": "A high-octane, visually mature Cyber-Noir thriller that honors the musical momentum through relentless forward camera vectors, tangible environmental physics, and strict character discipline."
    }


def analyze_music_with_agy(song_dir: Path, agy_bin: str = "agy", output_file: Path | None = None) -> dict:
    """Analyze music and write music_opinion.json."""
    song_dir = Path(song_dir).resolve()
    summary = build_song_summary(song_dir)

    user_prompt = f"""{CRITIC_SYSTEM_PROMPT}

SONG TO ANALYZE:
{json.dumps(summary, indent=2)}
"""

    print(f"[AGY Music Critic] Analyzing {song_dir.name}...")
    opinion = None

    # Step 1: Try agy CLI
    agy_raw = call_agy_cli(user_prompt, agy_bin)
    if agy_raw:
        try:
            # Clean markdown fences if any
            clean_text = agy_raw.strip()
            if clean_text.startswith("```"):
                clean_text = clean_text.split("```", 2)[1]
                if clean_text.startswith("json"):
                    clean_text = clean_text[4:].strip()
            opinion = json.loads(clean_text)
            print("  [OK] Successfully analyzed with Google Antigravity CLI (agy)!")
        except Exception as e:
            print(f"  [WARN] Could not parse agy output as JSON: {e}")

    # Step 2: Try Gemini API fallback
    if not opinion:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            # Check local .env files
            for p in [song_dir / ".env", song_dir.parent.parent / ".env", Path(r"X:\ChloeOSMaster\.env")]:
                if p.exists():
                    for line in p.read_text(encoding="utf-8-sig").splitlines():
                        if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
        if api_key:
            print("  [AGY Music Critic] Using Google GenAI endpoint fallback...")
            gemini_raw = call_gemini_api_fallback(user_prompt, api_key)
            if gemini_raw:
                try:
                    opinion = json.loads(gemini_raw)
                    print("  [OK] Successfully analyzed via Google GenAI!")
                except Exception:
                    pass

    # Step 3: Built-in deterministic structured critic
    if not opinion:
        print("  [AGY Music Critic] Compiling deterministic Maestro Director opinion...")
        opinion = generate_structured_critic_fallback(summary)

    # Save opinion
    dest = output_file or (song_dir / "music_opinion.json")
    dest.write_text(json.dumps(opinion, indent=2), encoding="utf-8")
    print(f"  [OK] Music critic opinion saved to: {dest.name}")
    return opinion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("song_dir", help="Path to song directory (e.g. songs/silicon_heartbeat)")
    parser.add_argument("--agy-bin", default="agy", help="Name or path of agy CLI binary")
    parser.add_argument("--output", "-o", help="Custom output JSON path")

    args = parser.parse_args()
    song_dir = Path(args.song_dir)
    if not song_dir.exists():
        sys.exit(f"Error: Song directory does not exist: {song_dir}")

    out = Path(args.output) if args.output else None
    analyze_music_with_agy(song_dir, agy_bin=args.agy_bin, output_file=out)


if __name__ == "__main__":
    main()
