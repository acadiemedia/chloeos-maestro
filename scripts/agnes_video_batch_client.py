#!/usr/bin/env python3
"""Agnes AI free text-to-video batch generator with variable duration support.

Usage:
    python agnes_video_batch_client.py --shotlist path/to/shotlist.json [--max 5] [--aspect landscape]
    python agnes_video_batch_client.py prompts.txt [--aspect landscape]

Generates real AI video clips via the Agnes Video V2.0 API (free tier: $0/sec,
500s/day, 1 RPM). Serial submission, poll-until-done, atomic download, JSONL log.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

API_HOST = "https://apihub.agnes-ai.com"
MODEL = "agnes-video-v2.0"

ASPECTS = {
    "landscape": {"width": 1152, "height": 648},
    "portrait":  {"width": 720,  "height": 1280},
    "square":    {"width": 768,  "height": 768},
}

SECONDS_DEFAULT = 4.0
FPS = 24

# ── API helpers ───────────────────────────────────────────────────────────────

def _req(url: str, key: str, method: str = "GET",
         payload: dict | None = None, timeout: int = 60):
    import urllib.request
    data = json.dumps(payload).encode() if payload else None
    headers = {"Authorization": f"Bearer {key}"}
    if payload:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def api_key() -> str:
    key = os.environ.get("AGNES_API_KEY")
    if not key:
        for env_path in [Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"]:
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip().lstrip('\ufeff')
                    if line.startswith("AGNES_API_KEY=") or line.startswith("AGNES_API_KEY ="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key:
                            os.environ["AGNES_API_KEY"] = key
                            break
            if key:
                break
    if not key:
        sys.exit("Error: set AGNES_API_KEY before running.")
    return key


def base_params(aspect: str, width: int | None = None,
                height: int | None = None, seconds: float = SECONDS_DEFAULT) -> dict:
    a = ASPECTS[aspect]
    sec = max(2, min(15, int(round(seconds))))
    return {
        "width": width or a["width"],
        "height": height or a["height"],
        "num_frames": sec * FPS + 1,
        "frame_rate": FPS,
    }


def create_task(prompt: str, key: str, params: dict) -> dict:
    return _req(f"{API_HOST}/v1/videos", key, method="POST",
                payload={"model": MODEL, "prompt": prompt, **params})


def poll_until_done(video_id: str, key: str,
                    max_wait: int = 600, interval: int = 8) -> dict:
    t0 = time.time()
    while time.time() - t0 < max_wait:
        resp = _req(f"{API_HOST}/agnesapi?video_id={video_id}", key)
        elapsed = int(time.time() - t0)
        status = resp.get("status")
        progress = resp.get("progress", 0)
        print(f"    [poll {elapsed:3d}s] {status} {progress}%", flush=True)
        if status == "completed":
            return resp
        if status == "failed":
            raise RuntimeError(f"task failed: {resp.get('error')}")
        time.sleep(interval)
    raise TimeoutError(f"video_id={video_id} did not finish in {max_wait}s")


def download(url: str, dest: Path, timeout: int = 300) -> bool:
    import shutil
    import urllib.request
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=timeout) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if tmp.stat().st_size == 0:
        tmp.unlink()
        return False
    tmp.replace(dest)
    return True


# ── Shotlist Mode ─────────────────────────────────────────────────────────────

def process_shotlist(shotlist_path: Path, args, key: str):
    data = json.load(open(shotlist_path, encoding="utf-8"))
    shots = data["shots"]
    custom_dir = getattr(args, "out_dir", None) or data.get("clips_dir")
    if custom_dir:
        clips_dir = shotlist_path.parent / custom_dir if not Path(custom_dir).is_absolute() else Path(custom_dir)
    else:
        clips_dir = shotlist_path.parent / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    log = shotlist_path.parent / "generation.log.jsonl"

    print(f"[batch] Processing {len(shots)} shots from {shotlist_path}")
    count = 0

    for s in shots:
        dest = clips_dir / f"shot_{s['shot']:03d}.mp4"
        s["clip_path"] = str(dest)

        if dest.exists() and dest.stat().st_size > 10000:
            print(f"[shot {s['shot']:03d}] already exists: {dest.name}")
            continue

        if args.max and count >= args.max:
            print(f"[batch] Reached limit of {args.max} generations.")
            break

        count += 1
        sec_dur = s.get("seconds", SECONDS_DEFAULT)
        params = base_params(args.aspect, args.width, args.height, seconds=sec_dur)
        prompt = s["prompt"]
        print(f"\n[{s['shot']:03d}/{len(shots)}] Generating {sec_dur}s clip:")
        print(f"    Prompt: {prompt[:85]}...")

        rec = {"shot": s["shot"], "prompt": prompt, "seconds": sec_dur}
        retries = 3
        while retries > 0:
            try:
                task = create_task(prompt, key, params)
                vid_id = task["video_id"]
                rec.update(task_id=task.get("id"), video_id=vid_id)
                print(f"    Task {task.get('id')} | Video {vid_id[:25]}...")

                done = poll_until_done(vid_id, key, interval=args.poll)
                url = done.get("url")
                if not url:
                    raise RuntimeError("completed but no URL returned")

                ok = download(url, dest)
                rec.update(status="ok" if ok else "download_failed", dest=str(dest))
                print(f"    [OK] Downloaded {dest.name}")
                break

            except Exception as exc:
                if "429" in str(exc) and retries > 1:
                    print(f"    [429 Rate Limit] Waiting 60s cooldown before retrying shot {s['shot']}...")
                    time.sleep(60)
                    retries -= 1
                else:
                    rec.update(status="error", error=str(exc))
                    print(f"    [FAIL] {exc}")
                    break

        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        # Save progress into shotlist
        with open(shotlist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        time.sleep(args.delay)

    print(f"\n[batch] Complete. Updated {shotlist_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("prompts", nargs="?", default=None,
                    help="text file with prompts")
    ap.add_argument("--shotlist", default=None,
                    help="path to shotlist.json")
    ap.add_argument("--out-dir", default=None,
                    help="custom output clips directory")
    ap.add_argument("--aspect", choices=list(ASPECTS), default="landscape")
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--max", type=int, default=0, help="max clips to generate (0 = all)")
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--poll", type=int, default=8)
    args = ap.parse_args()

    key = api_key()

    if args.shotlist:
        process_shotlist(Path(args.shotlist), args, key)
    elif args.prompts:
        # Standard txt mode
        p = Path(args.prompts)
        if not p.exists():
            sys.exit(f"File not found: {p}")
        # fallback to standard batch processing
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
