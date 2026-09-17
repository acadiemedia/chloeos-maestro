#!/usr/bin/env python3
"""ChloeOS Maestro Storyboard Curation & Approval Dashboard.

Serves an interactive dark-mode web GUI on localhost:8088 for reviewing
AGY music critique opinions, curating visual storyboards, editing shot prompts,
and approving blueprints prior to video synthesis.

Usage:
    python dashboard_app.py [songs/silicon_heartbeat] [--port 8088]
"""

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_SONG = Path(r"X:\chloeos-maestro\songs\silicon_heartbeat")
PORT = 8088

# ── HTML / CSS / JS UI ────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ChloeOS Maestro — Storyboard Curator & Approval</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body { background-color: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; }
    .badge-drop { background: rgba(248, 81, 73, 0.15); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.4); }
    .badge-verse { background: rgba(56, 139, 253, 0.15); color: #58a6ff; border: 1px solid rgba(56, 139, 253, 0.4); }
    .badge-intro { background: rgba(163, 113, 247, 0.15); color: #bc8cff; border: 1px solid rgba(163, 113, 247, 0.4); }
    .badge-climax { background: rgba(210, 153, 34, 0.15); color: #e3b341; border: 1px solid rgba(210, 153, 34, 0.4); }
    textarea:focus, input:focus, select:focus { outline: none; border-color: #58a6ff; }
  </style>
</head>
<body class="p-6">
  <div class="max-w-7xl mx-auto space-y-6">

    <!-- Header & Approval Banner -->
    <div class="card p-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-white tracking-tight" id="song-title">Loading Track...</h1>
          <span id="approval-badge" class="px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-yellow-900/40 text-yellow-400 border border-yellow-700">
            Pending Steve's Approval
          </span>
        </div>
        <p class="text-sm text-gray-400 mt-1">
          BPM: <span id="meta-bpm" class="font-mono text-cyan-400">120.0</span> &bull; 
          Duration: <span id="meta-dur" class="font-mono text-cyan-400">180.000s</span> &bull; 
          Shots: <span id="meta-shots" class="font-mono text-cyan-400">21</span>
        </p>
      </div>

      <div class="flex items-center gap-3">
        <button onclick="saveStoryboard()" class="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium border border-gray-600 transition">
          💾 Save Edits
        </button>
        <button onclick="generateAnchors()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition shadow-lg">
          🎨 Generate Imagen 3 Anchors
        </button>
        <button onclick="approveStoryboard()" id="btn-approve" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-bold tracking-wide transition shadow-lg flex items-center gap-2">
          ✓ Approve Storyboard
        </button>
      </div>
    </div>

    <!-- AGY Music Critic Opinion Panel -->
    <div class="card p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-gray-800 pb-3">
        <div class="flex items-center gap-2">
          <span class="text-cyan-400 text-lg font-bold">⚡ Google Antigravity CLI (agy) Opinion</span>
          <span class="text-xs bg-cyan-950 text-cyan-300 px-2 py-0.5 rounded border border-cyan-800">Acoustic & Structural Intelligence</span>
        </div>
        <button onclick="refreshOpinion()" class="text-xs text-gray-400 hover:text-white">Re-analyze with agy</button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div class="bg-gray-900/50 p-4 rounded-lg border border-gray-800 space-y-2">
          <div class="text-xs uppercase font-semibold text-gray-400">Overall Mood & Narrative Arc</div>
          <p id="agy-mood" class="text-gray-200 leading-relaxed">Analyzing...</p>
        </div>
        <div class="bg-gray-900/50 p-4 rounded-lg border border-gray-800 space-y-2">
          <div class="text-xs uppercase font-semibold text-gray-400">Director's Production Vision</div>
          <p id="agy-summary" class="text-gray-200 leading-relaxed">Analyzing...</p>
        </div>
      </div>

      <div class="bg-gray-900/30 p-3 rounded border border-gray-800">
        <div class="text-xs uppercase font-semibold text-gray-400 mb-2">Director Directives for Visual Storyboard</div>
        <ul id="agy-directives" class="list-disc list-inside text-xs text-gray-300 space-y-1"></ul>
      </div>
    </div>

    <!-- Storyboard Shots Grid -->
    <div>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-white">Visual Storyboard Shots (<span id="shot-count">0</span>)</h2>
        <span class="text-xs text-gray-400">Edit scene titles, camera movements, and prompts below</span>
      </div>

      <div id="shots-container" class="space-y-4">
        <!-- Shot Cards Rendered Dynamically -->
      </div>
    </div>

  </div>

  <script>
    let currentStoryboard = null;
    let currentOpinion = null;

    async function loadData() {
      try {
        const res = await fetch('/api/data');
        const data = await res.json();
        currentStoryboard = data.storyboard;
        currentOpinion = data.opinion;
        renderUI();
      } catch (err) {
        console.error("Error loading data:", err);
      }
    }

    function renderUI() {
      if (!currentStoryboard) return;

      document.getElementById('song-title').innerText = currentStoryboard.title || "Track Storyboard";
      document.getElementById('meta-bpm').innerText = (currentStoryboard.bpm || 120.0).toFixed(1);
      document.getElementById('meta-dur').innerText = (currentStoryboard.duration || 180.0).toFixed(3) + 's';
      document.getElementById('meta-shots').innerText = (currentStoryboard.shots || []).length;
      document.getElementById('shot-count').innerText = (currentStoryboard.shots || []).length;

      const badge = document.getElementById('approval-badge');
      const btnApprove = document.getElementById('btn-approve');
      if (currentStoryboard.approved) {
        badge.innerText = "✓ Approved by Steve";
        badge.className = "px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-emerald-950 text-emerald-400 border border-emerald-700";
        btnApprove.innerText = "✓ Storyboard Approved";
        btnApprove.disabled = true;
        btnApprove.className = "px-5 py-2 bg-emerald-800 text-gray-300 rounded-lg text-sm font-bold opacity-60 cursor-not-allowed";
      } else {
        badge.innerText = "Pending Steve's Approval";
        badge.className = "px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider bg-yellow-900/40 text-yellow-400 border border-yellow-700";
        btnApprove.innerText = "✓ Approve Storyboard";
        btnApprove.disabled = false;
        btnApprove.className = "px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-bold tracking-wide transition shadow-lg flex items-center gap-2";
      }

      if (currentOpinion) {
        document.getElementById('agy-mood').innerText = currentOpinion.overall_mood || "No mood defined";
        document.getElementById('agy-summary').innerText = currentOpinion.director_summary || "No summary available";
        const dirList = document.getElementById('agy-directives');
        dirList.innerHTML = (currentOpinion.visual_storyboard_directives || []).map(d => `<li>${d}</li>`).join('');
      }

      const container = document.getElementById('shots-container');
      container.innerHTML = (currentStoryboard.shots || []).map((s, idx) => {
        let badgeClass = "badge-verse";
        const sec = (s.section || "").toLowerCase();
        if (sec.includes("intro")) badgeClass = "badge-intro";
        else if (sec.includes("drop")) badgeClass = "badge-drop";
        else if (sec.includes("climax") || sec.includes("outro")) badgeClass = "badge-climax";

        return `
          <div class="card p-5 space-y-4">
            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-800/80 pb-3">
              <div class="flex items-center gap-3">
                <span class="font-mono text-cyan-400 font-bold text-base">#${String(s.shot).padStart(2, '0')}</span>
                <span class="px-2.5 py-0.5 rounded text-xs font-medium ${badgeClass}">${s.section || "Scene"}</span>
                <span class="text-xs text-gray-400 font-mono">${s.t_start.toFixed(1)}s &rarr; ${(s.t_start + s.duration).toFixed(1)}s (${s.duration.toFixed(1)}s)</span>
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-400">Camera Grammar:</label>
                <input type="text" value="${s.camera || ''}" onchange="updateShot(${idx}, 'camera', this.value)"
                  class="bg-gray-900 border border-gray-700 text-xs text-white rounded px-2.5 py-1 w-64">
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-12 gap-4">
              <div class="md:col-span-8 space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-xs font-semibold text-gray-300">Visual Prompt:</label>
                  <span class="text-xs text-gray-500">Includes Chloe & Vehicle Anchors</span>
                </div>
                <textarea rows="3" onchange="updateShot(${idx}, 'prompt', this.value)"
                  class="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs text-gray-200 leading-relaxed">${s.prompt || ''}</textarea>
              </div>

              <div class="md:col-span-4 bg-gray-900/50 rounded-lg border border-gray-800 p-3 flex flex-col justify-between">
                <div>
                  <div class="text-xs font-semibold text-gray-400 mb-1">Visual Anchor Frame</div>
                  <div class="text-xs text-gray-500 truncate mb-2">${s.anchor_image_path ? s.anchor_image_path.split('\\\\').pop() : 'No plate generated yet'}</div>
                </div>
                <div class="flex items-center justify-between mt-2 pt-2 border-t border-gray-800">
                  <span class="text-xs ${s.anchor_image_path ? 'text-emerald-400' : 'text-gray-500'}">
                    ${s.anchor_image_path ? '● Anchor Ready' : '○ Missing'}
                  </span>
                  <button onclick="generateSingleAnchor(${s.shot})" class="text-xs px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-cyan-300 rounded border border-gray-700">
                    Gen Anchor
                  </button>
                </div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function updateShot(idx, field, value) {
      if (currentStoryboard && currentStoryboard.shots[idx]) {
        currentStoryboard.shots[idx][field] = value;
      }
    }

    async function saveStoryboard() {
      try {
        const res = await fetch('/api/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentStoryboard)
        });
        const result = await res.json();
        if (result.ok) alert("✓ Storyboard saved successfully!");
        else alert("Error saving storyboard: " + result.error);
      } catch (err) {
        alert("Network error saving storyboard: " + err);
      }
    }

    async function approveStoryboard() {
      if (!confirm("Are you sure you want to approve this storyboard? This will lock the shotlist for Google Imagen 3 anchors and video generation.")) return;
      try {
        currentStoryboard.approved = true;
        currentStoryboard.status = "approved_by_steve";
        const res = await fetch('/api/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentStoryboard)
        });
        const result = await res.json();
        if (result.ok) {
          alert("✓ Storyboard APPROVED! You can now proceed to Google Imagen 3 anchors and Video synthesis.");
          renderUI();
        } else {
          alert("Approval failed: " + result.error);
        }
      } catch (err) {
        alert("Error approving storyboard: " + err);
      }
    }

    async function generateAnchors() {
      alert("Launching Google Imagen 3 anchor plate batch in background...");
      await fetch('/api/generate_anchors', { method: 'POST' });
    }

    async function generateSingleAnchor(shotNum) {
      alert("Generating Google Imagen 3 anchor for Shot #" + shotNum + "...");
      await fetch('/api/generate_single_anchor?shot=' + shotNum, { method: 'POST' });
      loadData();
    }

    async function refreshOpinion() {
      if (!confirm("Re-analyze track with Google Antigravity CLI (agy)?")) return;
      await fetch('/api/refresh_opinion', { method: 'POST' });
      alert("Re-analysis triggered! Refreshing...");
      setTimeout(loadData, 3000);
    }

    loadData();
  </script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    song_dir = DEFAULT_SONG

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif parsed.path == "/api/data":
            self.handle_get_data()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        if parsed.path == "/api/save":
            self.handle_save(post_data)
        elif parsed.path == "/api/approve":
            self.handle_approve(post_data)
        elif parsed.path == "/api/generate_anchors":
            self.handle_generate_anchors()
        elif parsed.path == "/api/generate_single_anchor":
            params = parse_qs(parsed.query)
            shot_num = int(params.get("shot", [1])[0])
            self.handle_single_anchor(shot_num)
        elif parsed.path == "/api/refresh_opinion":
            self.handle_refresh_opinion()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_get_data(self):
        song_dir = self.song_dir
        storyboard_file = song_dir / "storyboard.json"
        opinion_file = song_dir / "music_opinion.json"

        storyboard = {}
        opinion = {}
        if storyboard_file.exists():
            try:
                storyboard = json.loads(storyboard_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if opinion_file.exists():
            try:
                opinion = json.loads(opinion_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"storyboard": storyboard, "opinion": opinion}).encode("utf-8"))

    def handle_save(self, post_data: str):
        try:
            data = json.loads(post_data)
            out_file = self.song_dir / "storyboard.json"
            out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))

    def handle_approve(self, post_data: str):
        try:
            data = json.loads(post_data)
            data["approved"] = True
            data["status"] = "approved_by_steve"
            out_file = self.song_dir / "storyboard.json"
            out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            # Also update shotlist.json to sync approval
            shotlist_file = self.song_dir / "shotlist.json"
            if shotlist_file.exists():
                try:
                    s_data = json.loads(shotlist_file.read_text(encoding="utf-8"))
                    s_data["approved"] = True
                    shotlist_file.write_text(json.dumps(s_data, indent=2), encoding="utf-8")
                except Exception:
                    pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))

    def handle_generate_anchors(self):
        scripts_dir = Path(__file__).parent
        shotlist_file = self.song_dir / "storyboard.json"
        cmd = [sys.executable, str(scripts_dir / "google_image_generator.py"), "--shotlist", str(shotlist_file)]
        subprocess.Popen(cmd)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "status": "started"}).encode("utf-8"))

    def handle_single_anchor(self, shot_num: int):
        # find prompt
        storyboard_file = self.song_dir / "storyboard.json"
        if storyboard_file.exists():
            data = json.loads(storyboard_file.read_text(encoding="utf-8"))
            shot = next((s for s in data.get("shots", []) if s.get("shot") == shot_num), None)
            if shot:
                scripts_dir = Path(__file__).parent
                out_file = self.song_dir / "anchors" / f"shot_{shot_num:03d}_anchor.jpg"
                out_file.parent.mkdir(parents=True, exist_ok=True)
                cmd = [sys.executable, str(scripts_dir / "google_image_generator.py"),
                       "--prompt", shot.get("prompt", ""), "--output", str(out_file)]
                subprocess.Popen(cmd)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def handle_refresh_opinion(self):
        scripts_dir = Path(__file__).parent
        cmd = [sys.executable, str(scripts_dir / "agy_music_critic.py"), str(self.song_dir)]
        subprocess.Popen(cmd)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))


def run_dashboard(song_dir: Path, port: int = PORT, open_browser: bool = True):
    DashboardHandler.song_dir = Path(song_dir).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f"   CHLOEOS MAESTRO STORYBOARD CURATOR & APPROVAL GUI")
    print(f"=======================================================")
    print(f"  Track: {DashboardHandler.song_dir.name}")
    print(f"  Dashboard running at: {url}")
    print(f"  Press Ctrl+C to stop the dashboard.\n")

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Dashboard] Shutting down...")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("song_dir", nargs="?", default=str(DEFAULT_SONG), help="Path to song directory")
    parser.add_argument("--port", type=int, default=PORT, help="Port to serve on")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch browser")

    args = parser.parse_args()
    run_dashboard(Path(args.song_dir), port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
