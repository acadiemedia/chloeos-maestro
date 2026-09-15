#!/usr/bin/env python3
"""Agnes AI free text-to-video batch generator.

    python3 agnes_video_batch.py prompts.txt --aspect portrait

Generates real AI video clips via the Agnes Video V2.0 API (free tier: $0/sec,
500s/day, 1 RPM). Serial submission, poll-until-done, atomic download, JSONL log.

Env:    AGNES_API_KEY   (sk-... key from platform.agnes-ai.com)
Deps:   stdlib only (urllib.request) — no pip installs needed.

See: AGNES_API_REFERENCE.md  |  batch_engine.md  |  prompt_guide.md
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

FRAMES_PER_SEC = 24      # fancier: num_frames maps to duration via fps
SECONDS_DEFAULT = 4.0
FPS = 24

# ── API helpers (stdlib only) ─────────────────────────────────────────────────

def _req(url: str, key: str, method: str = "GET",
         payload: dict | None = None, timeout: int = 60):
    """Single-point HTTP request. Returns parsed JSON."""
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
        sys.exit("Error: set AGNES_API_KEY before running.\n"
                 "  export AGNES_API_KEY='sk-...'   # from platform.agnes-ai.com/settings/apiKeys")
    return key


def base_params(aspect: str, width: int | None = None,
                height: int | None = None, seconds: float = SECONDS_DEFAULT) -> dict:
    a = ASPECTS[aspect]
    return {
        "width": width or a["width"],
        "height": height or a["height"],
        "num_frames": round(seconds * FPS) + 1,
        "frame_rate": FPS,
    }


# ── Core pipeline ─────────────────────────────────────────────────────────────

def create_task(prompt: str, key: str, params: dict) -> dict:
    """POST /v1/videos → queued task with task_id + video_id."""
    return _req(f"{API_HOST}/v1/videos", key, method="POST",
                payload={"model": MODEL, "prompt": prompt, **params})


def poll_until_done(video_id: str, key: str,
                    max_wait: int = 600, interval: int = 8) -> dict:
    """Poll GET /agnesapi?video_id= until completed or failed."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        resp = _req(f"{API_HOST}/agnesapi?video_id={video_id}", key)
        elapsed = int(time.time() - t0)
        status  = resp.get("status")
        progress = resp.get("progress", 0)
        print(f"    [poll {elapsed:3d}s] {status} {progress}%", flush=True)
        if status == "completed":
            return resp
        if status == "failed":
            raise RuntimeError(f"task failed: {resp.get('error')}")
        time.sleep(interval)
    raise TimeoutError(f"video_id={video_id} did not finish in {max_wait}s")


def download(url: str, dest: Path, timeout: int = 300) -> bool:
    """Stream-download MP4 via atomic .part → rename."""
    import shutil
    tmp = dest.with_suffix(dest.suffix + ".part")
    import urllib.request
    with urllib.request.urlopen(url, timeout=timeout) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if tmp.stat().st_size == 0:
        tmp.unlink()
        return False
    tmp.replace(dest)
    return True


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  %(prog)s prompts.txt --aspect portrait          # → ./prompts/clips/\n"
               "  %(prog)s prompts.txt --aspect landscape --max 5\n"
               "  %(prog)s prompts.txt --out ~/content --width 1920 --height 1080\n",
    )
    ap.add_argument("prompts",
                    help="text file with one prompt per line (# comments, blank lines ignored)")
    ap.add_argument("--out",    default=None,
                    help="project folder (default: ./<prompt_file_name>/ — self-named)")
    ap.add_argument("--aspect", choices=list(ASPECTS), default="landscape",
                    help="landscape (1152x648) | portrait (720x1280) | square (768x768)")
    ap.add_argument("--width",  type=int, default=None, help="override width (pixels)")
    ap.add_argument("--height", type=int, default=None, help="override height (pixels)")
    ap.add_argument("--max",    type=int, default=0,    help="max clips to generate (0 = all)")
    ap.add_argument("--delay",  type=float, default=4.0, help="seconds between submissions")
    ap.add_argument("--poll",   type=int,   default=8,   help="seconds between status polls")
    ap.add_argument("--seconds", type=float, default=SECONDS_DEFAULT,
                    help="clip duration in seconds (default: 4, max: 15)")
    args = ap.parse_args()

    key = api_key()

    # Single self-named project folder: <out>/clips, <out>/batch.log.jsonl,
    # <out>/prompts.txt. Default name = prompt file name (e.g. awaken_prompts.txt → ./awaken/)
    stem = Path(args.prompts).stem.replace("_prompts", "").replace("_prompt", "") or "project"
    project = Path(args.out) if args.out else Path.cwd() / stem
    clips_dir = project / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    log = project / "batch.log.jsonl"
    (project / "prompts.txt").write_text(Path(args.prompts).read_text())

    prompts = [l.strip() for l in Path(args.prompts).read_text().splitlines()
               if l.strip() and not l.strip().startswith("#")]
    if args.max:
        prompts = prompts[: args.max]

    params = base_params(args.aspect, args.width, args.height, seconds=args.seconds)
    print(f"[batch] {len(prompts)} clips × {args.seconds}s → {project}  ({args.aspect} {params['width']}x{params['height']})",
          flush=True)

    results = []
    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {prompt[:72]}...", flush=True)
        rec = {"index": i, "prompt": prompt}
        try:
            task    = create_task(prompt, key, params)
            vid_id  = task["video_id"]
            rec.update(task_id=task.get("id"), video_id=vid_id,
                       status_create=task.get("status"))
            print(f"    task {task['id']}  video {vid_id[:28]}...", flush=True)

            done = poll_until_done(vid_id, key, interval=args.poll)
            url  = done.get("url")
            if not url:
                raise RuntimeError("completed but no url")

            safe = "".join(c for c in prompt if c.isalnum() or c in "-_ ").strip().replace(" ", "_")[:50] or "v"
            dest = clips_dir / f"{i:03d}_{safe}.mp4"
            ok   = download(url, dest)
            rec.update(status="ok" if ok else "download_failed", dest=str(dest), url=url)
            print(f"    ✓ {dest.name}", flush=True)

        except Exception as exc:
            rec.update(status="error", error=str(exc))
            print(f"    ✗ {exc}", flush=True)

        with log.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        results.append(rec)
        if i < len(prompts):
            time.sleep(args.delay)

    n_ok = sum(r["status"] == "ok" for r in results)
    print(f"\n[batch] done: {n_ok}/{len(results)} ok — log: {log}", flush=True)


if __name__ == "__main__":
    main()
