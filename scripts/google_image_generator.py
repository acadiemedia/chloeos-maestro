#!/usr/bin/env python3
"""Google Image Generation Client (Imagen 3) for ChloeOS Maestro.

Generates photorealistic visual anchor stills, character reference plates,
and Image-to-Video (I2V) starting frames using Google's Imagen 3 API.

Usage:
    # Generate anchor plates from a shotlist:
    python google_image_generator.py --shotlist path/to/shotlist.json [--out-dir anchors] [--aspect 16:9]

    # Generate a single anchor image:
    python google_image_generator.py --prompt "Cinematic wide shot of Chloe..." --output chloe_anchor.jpg [--aspect 16:9]
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Defaults & Constants ──────────────────────────────────────────────────────

IMAGEN_MODEL = "imagen-3.0-generate-002"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN_MODEL}:predict"

ASPECT_RATIOS = ["16:9", "1:1", "9:16", "4:3", "3:4"]

CHLOE_CHARACTER_ANCHOR = (
    "A stunning beautiful Caucasian woman with sleek straight raven jet-black hair, "
    "striking luminous blue eyes, wearing a tailored futuristic white tactical flight suit. "
    "Cinematic lighting, 35mm film grain, photorealistic 8k, photoreal masterpiece."
)

RABBIT_COMPANION_ANCHOR = (
    "A cute small white rabbit wearing round nerd glasses, with a gold compass glowing "
    "bright cyan-blue around its neck."
)


# ── API Key Resolution ────────────────────────────────────────────────────────

def get_api_key() -> str:
    """Resolve Gemini / Google API key from env or common config paths."""
    for var in ["GEMINI_API_KEY", "GOOGLE_API_KEY"]:
        val = os.environ.get(var)
        if val:
            return val

    # Check local .env files
    search_paths = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(r"X:\ChloeOSMaster\.env"),
        Path(r"X:\chloeos-maestro\.env"),
    ]
    for p in search_paths:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip().lstrip('\ufeff')
                    for prefix in ["GEMINI_API_KEY=", "GOOGLE_API_KEY="]:
                        if line.startswith(prefix):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                os.environ["GEMINI_API_KEY"] = val
                                return val
            except Exception:
                pass

    return ""


# ── Image Generation via Google Imagen 3 ──────────────────────────────────────

def generate_image_imagen3(
    prompt: str,
    api_key: str,
    aspect_ratio: str = "16:9",
    number_of_images: int = 1,
    person_generation: str = "ALLOW_ADULT",
    safety_filter_level: str = "BLOCK_ONLY_HIGH",
    output_mime_type: str = "image/jpeg",
) -> list[bytes]:
    """Call Google Generative Language Imagen 3 endpoint and return image bytes."""
    if not api_key:
        raise ValueError(
            "Missing Google/Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY."
        )

    url = f"{API_URL}?key={api_key}"

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": number_of_images,
            "aspectRatio": aspect_ratio,
            "personGeneration": person_generation,
            "safetyFilterLevel": safety_filter_level,
            "outputMimeType": output_mime_type,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Google Imagen 3 API error ({e.code}): {err_msg}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to connect to Google Imagen 3 API: {e}") from e

    predictions = body.get("predictions", [])
    if not predictions:
        raise RuntimeError(f"No image predictions returned: {body}")

    results = []
    for pred in predictions:
        b64_str = pred.get("bytesBase64Encoded")
        if b64_str:
            results.append(base64.b64decode(b64_str))

    return results


# ── Shotlist Batch Mode ───────────────────────────────────────────────────────

def process_shotlist(
    shotlist_path: Path,
    out_dir: Path | None = None,
    aspect: str = "16:9",
    max_count: int = 0,
    api_key: str = "",
):
    """Generate anchor frames for all shots in a Maestro shotlist."""
    shotlist_path = Path(shotlist_path).resolve()
    data = json.loads(shotlist_path.read_text(encoding="utf-8"))
    shots = data.get("shots", [])

    if out_dir:
        anchors_dir = Path(out_dir).resolve()
    else:
        anchors_dir = shotlist_path.parent / "anchors"
    anchors_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Maestro Imagen 3] Processing {len(shots)} shots from {shotlist_path.name}")
    print(f"[Maestro Imagen 3] Output directory: {anchors_dir}")

    count = 0
    for s in shots:
        shot_num = s.get("shot", 0)
        out_file = anchors_dir / f"shot_{shot_num:03d}_anchor.jpg"
        s["anchor_image_path"] = str(out_file)

        if out_file.exists() and out_file.stat().st_size > 5000:
            print(f"  [shot {shot_num:03d}] Anchor exists: {out_file.name}")
            continue

        if max_count and count >= max_count:
            print(f"  [Maestro Imagen 3] Reached limit of {max_count} generations.")
            break

        count += 1
        prompt = s.get("prompt", "")
        print(f"\n  [{shot_num:03d}/{len(shots)}] Generating Google Imagen 3 anchor:")
        print(f"    Prompt: {prompt[:85]}...")

        retries = 3
        while retries > 0:
            try:
                img_bytes_list = generate_image_imagen3(
                    prompt=prompt,
                    api_key=api_key,
                    aspect_ratio=aspect,
                )
                if img_bytes_list:
                    out_file.write_bytes(img_bytes_list[0])
                    print(f"    [OK] Saved anchor plate: {out_file.name} ({len(img_bytes_list[0]) // 1024} KB)")
                    break
                else:
                    raise RuntimeError("Empty image response")
            except Exception as e:
                retries -= 1
                print(f"    [WARN] Error generating shot {shot_num:03d}: {e}")
                if retries > 0:
                    print("    Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print(f"    [FAILED] Shot {shot_num:03d} failed.")

        # Modest delay between generations
        time.sleep(2)

    # Save updated shotlist with anchor paths
    shotlist_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\n[OK] Anchor generation complete! Shotlist updated with anchor image paths.")


# ── CLI Entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shotlist", help="Path to Maestro shotlist.json")
    parser.add_argument("--prompt", help="Single prompt for anchor generation")
    parser.add_argument("--output", "-o", help="Output file path for single prompt mode")
    parser.add_argument("--out-dir", help="Output directory for shotlist anchor plates")
    parser.add_argument("--aspect", default="16:9", choices=ASPECT_RATIOS, help="Aspect ratio")
    parser.add_argument("--max", type=int, default=0, help="Max images to generate (0 = all)")
    parser.add_argument("--key", help="Google/Gemini API Key override")

    args = parser.parse_args()

    key = args.key or get_api_key()
    if not key:
        print("ERROR: No Google / Gemini API key found.")
        print("Please set GEMINI_API_KEY in your environment or pass via --key.")
        sys.exit(1)

    if args.shotlist:
        process_shotlist(
            Path(args.shotlist),
            out_dir=Path(args.out_dir) if args.out_dir else None,
            aspect=args.aspect,
            max_count=args.max,
            api_key=key,
        )
    elif args.prompt:
        out_path = Path(args.output or "anchor_output.jpg")
        print(f"[Maestro Imagen 3] Generating single plate: {out_path.name}")
        images = generate_image_imagen3(
            prompt=args.prompt,
            api_key=key,
            aspect_ratio=args.aspect,
        )
        if images:
            out_path.write_bytes(images[0])
            print(f"[OK] Saved {out_path} ({len(images[0]) // 1024} KB)")
        else:
            sys.exit("[FAILED] No image returned.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
