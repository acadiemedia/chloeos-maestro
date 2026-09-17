import re
import json
from pathlib import Path

vtt_path = Path(r"X:\chloeos-maestro\assets\silicon_heartbeat\silicon_heartbeat.en.vtt")
vtt = vtt_path.read_text(encoding="utf-8")
blocks = vtt.split("\n\n")
lines = []
last_text = ""

def parse_time(ts):
    parts = ts.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h)*3600 + int(m)*60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m)*60 + float(s)
    return float(ts)

for b in blocks:
    m = re.search(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})", b)
    if not m:
        continue
    t0 = parse_time(m.group(1))
    t1 = parse_time(m.group(2))
    raw_lines = b.splitlines()
    text_lines = [l for l in raw_lines if "-->" not in l and not l.startswith("WEBVTT") and not l.startswith("Kind:") and not l.startswith("Language:")]
    clean_text = " ".join(text_lines)
    clean_text = re.sub(r"<[^>]+>", "", clean_text)
    clean_text = re.sub(r"&gt;&gt;\s*", "", clean_text)
    clean_text = clean_text.replace("[music]", "").strip()
    if clean_text and clean_text != last_text:
        # Avoid duplicate overlapping lines from karaoke VTT
        if not lines or not (lines[-1]["text"].endswith(clean_text) or clean_text in lines[-1]["text"]):
            lines.append({"t_start": round(t0, 3), "t_end": round(t1, 3), "text": clean_text})
            last_text = clean_text

out_json = Path(r"X:\chloeos-maestro\assets\silicon_heartbeat\lyrics_clean.json")
out_json.write_text(json.dumps(lines, indent=2), encoding="utf-8")
print(f"Extracted {len(lines)} lyric cues to {out_json}")
for l in lines:
    print(f"[{l['t_start']:6.2f} - {l['t_end']:6.2f}] {l['text']}")
