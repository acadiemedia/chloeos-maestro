#!/usr/bin/env python3
"""Professional music analysis → music vector database (JSON).

Extracts a complete musical fingerprint from a track:
  * onset envelope & spectral flux
  * global BPM (estimated+refined)
  * every beat (t, bar, beat_in_bar, is_downbeat, onset_strength, energy)
  * bar grid + 2/4/8/16/32-beat markers
  * energy / RMS curve (1-per-beat, 1-per-bar)
  * momentum (Δenergy) for rise/fall detection
  * sections (intro/verse/chorus/drop/breakdown/outro style segmentation)
  * drop events (peak + payoff after steep accumulated rise)
  * downbeat-aligned structural markers

Output: JSON with beats[], bars[], markers{}, sections[], drops[], curve[].
"""
import json
import sys
import numpy as np
import librosa

SR = 44100
HOP = 512  # ~11.6ms resolution


def rms(y):
    return librosa.feature.rms(y=y, hop_length=HOP)[0]


def onset_env(y):
    # spectral flux onset strength (max-based peak picks well for EDM/house)
    return librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP, n_fft=2048, aggregate=np.median)


def frames_to_times(frames):
    return librosa.frames_to_time(frames, sr=SR, hop_length=HOP)


def main(path, out_path, title="untitled"):
    y, sr = librosa.load(path, sr=SR, mono=True)

    duration = librosa.get_duration(y=y, sr=SR)
    oenv = onset_env(y)
    energy = rms(y)
    times = frames_to_times(np.arange(len(oenv)))

    # ---- tempo ----
    tempo, beats = librosa.beat.beat_track(
        onset_envelope=oenv, sr=SR, hop_length=HOP,
        trim=True, units="frames")
    tempo = float(np.round(np.atleast_1d(tempo)[0]))
    beats = np.asarray(beats)
    if beats.ndim > 1:
        beats = beats[0]
    beat_frames = beats
    beat_times = frames_to_times(beat_frames)

    if len(beat_times) < 8:
        sys.exit("Could not detect enough beats")

    beat_period = np.median(np.diff(beat_times))

    # ---- downbeat phase estimation ----
    # For 4/4: assume 4 beats/bar. Phase = offset starting bar that maximises
    # accumulated onset energy (downbeats usually carry the most).
    beats_energy = np.interp(beat_times, times, oenv)
    best_phase, best_score = 0, -1
    for phase in range(4):
        score = beats_energy[phase::4].sum()
        if score > best_score:
            best_score, best_phase = score, phase
    downbeat_idx = list(range(best_phase, len(beat_times), 4))

    # ---- continuous grid projected across the WHOLE track ----
    # Fit a global grid {t = grid_t0 + n*beat_period} through the detected beats
    # (median intercept), then extend backwards to t≈0 so the intro gets grid too.
    n = np.arange(len(beat_times))
    grid_t0 = float(np.median(beat_times - n * beat_period))
    n_total = int(np.ceil(duration / beat_period)) + 2
    grid_n = np.arange(n_total)
    grid_times = grid_t0 + grid_n * beat_period
    grid_times = grid_times[grid_times <= duration + beat_period / 2]

    # only beats already contain music onset: mark which grid beats are detected
    detected = np.isin(grid_times, beat_times)

    grid_energy = np.interp(grid_times, times, energy)
    grid_oenv = np.interp(grid_times, times, oenv)

    grid_bar = grid_n[: len(grid_times)] // 4
    grid_beat_in_bar = (grid_n[: len(grid_times)] % 4) + 1

    beats_out = []
    for i, t in enumerate(grid_times):
        beats_out.append({
            "t": round(float(t), 6),
            "index": i,
            "bar": int(grid_bar[i]),
            "beat_in_bar": int(grid_beat_in_bar[i]),
            "is_downbeat": int(grid_beat_in_bar[i]) == 1,
            "detected": bool(detected[i]),
            "onset": round(float(grid_oenv[i]), 6),
            "energy": round(float(grid_energy[i]), 6),
        })

    # ---- bar grid & markers (from projected grid) ----
    bars = {}
    n_beats = len(grid_times)
    for k in (1, 2, 4, 8, 16, 32):
        step = k * 4  # bars in beats
        idxs = list(range(0, n_beats, step))
        bars[f"{k * 4}_beat"] = {
            "count": len(idxs),
            "marks": [round(float(grid_times[i]), 6) for i in idxs],
        }

    # ---- energy curves per bar ----
    n_bars = int(grid_bar.max()) + 1  # using projected grid
    bar_energy = np.zeros(n_bars)
    bar_onset = np.zeros(n_bars)
    for i in range(n_beats):
        b = int(grid_bar[i])
        bar_energy[b] = max(bar_energy[b], beats_out[i]["energy"])
        bar_onset[b] += beats_out[i]["onset"]
    bar_times = np.array([grid_times[b * 4] if b * 4 < n_beats else times[-1]
                          for b in range(n_bars)])

    # ---- sections: moving-average energy level zoning ----
    # smooth bar energy, then label by z-score thresholds
    k = 5
    kernel = np.ones(k) / k
    smooth = np.convolve(bar_energy, kernel, mode="same")
    mu, sd = smooth.mean(), smooth.std()
    hi = mu + 0.5 * sd
    mid = mu - 0.15 * sd

    labels = []
    for e in smooth:
        if e >= hi:
            labels.append("drop_chorus")
        elif e <= mid:
            labels.append("low_intro_outro")
        else:
            labels.append("build_mid")

    # merge runs into sections
    sections = []
    start_bar = 0
    cur = labels[0]
    for i in range(1, n_bars + 1):
        lab = labels[i] if i < n_bars else None
        if lab != cur:
            t0 = grid_times[start_bar * 4] if start_bar * 4 < n_beats else times[-1]
            t1 = grid_times[(i - 1) * 4 + 3] if (i - 1) * 4 + 3 < n_beats else times[-1]
            sections.append({
                "t_start": round(float(t0), 6),
                "t_end": round(float(t1), 6),
                "bar_start": int(start_bar),
                "bar_end": int(i - 1),
                "zone": cur,
                "avg_energy": round(float(smooth[start_bar:i].mean()), 6),
                "peak_energy": round(float(smooth[start_bar:i].max()), 6),
            })
            start_bar = i
            cur = lab

    # ---- momentum (derivative of bar energy → rise up / charge / fade) ----
    momentum = np.gradient(smooth)

    # ---- drops: find REAL high-energy events, de-cluster ----
    # candidate peak bars above the high threshold, then merge peaks within
    # ±2 bars (8 beats) keeping the strongest; each drop must sit after a climb.
    candidates = []
    for i in range(1, n_bars - 1):
        if (smooth[i] >= hi and
                smooth[i] >= smooth[i - 1] and
                smooth[i] >= smooth[i + 1] and
                momentum[i - 1] > 0.05 * momentum.max()):
            candidates.append(i)
    drops = []
    for i in candidates:
        if drops and i - drops[-1]["drop_bar"] <= 2:
            if smooth[i] > drops[-1]["peak_energy"]:
                drops[-1] = {
                    "drop_bar": int(i),
                    "t": round(float(bar_times[i]), 6),
                    "peak_energy": round(float(smooth[i]), 6),
                    "rise_bars": int(i),
                }
        else:
            drops.append({
                "drop_bar": int(i),
                "t": round(float(bar_times[i]), 6),
                "peak_energy": round(float(smooth[i]), 6),
                "rise_bars": int(i),
            })

    doc = {
        "meta": {
            "title": title,
            "duration_sec": round(float(duration), 6),
            "sample_rate": SR,
            "hop": HOP,
        },
        "tempo": {
            "bpm": tempo,
            "beat_period_sec": round(float(beat_period), 6),
            "beats_total": n_beats,
            "bars_total": n_bars,
            "meter": "4/4",
            "downbeats_total": len(downbeat_idx),
        },
        "beats": beats_out,
        "markers": bars,
        "sections": sections,
        "drops": drops,
        "curve": {
            "n_pts": int(len(times)),
            "times": [round(float(t), 6) for t in times[::2]],
            "energy": [round(float(e), 6) for e in energy[::2]],
            "onset":  [round(float(v), 6) for v in oenv[::2]],
        },
        "bar_curve": {
            "t": [round(float(t), 6) for t in bar_times],
            "energy": [round(float(e), 6) for e in bar_energy],
            "smooth": [round(float(e), 6) for e in smooth],
            "momentum": [round(float(m), 6) for m in momentum],
        },
        "grid": {
            "beat0_t": round(float(beat_times[0]), 6),
            "beat_period_sec": round(float(beat_period), 6),
        },
    }

    with open(out_path, "w") as f:
        json.dump(doc, f, indent=1)

    # console digest
    print(f"[analyze] {title}  {duration:.1f}s")
    print(f"  BPM {tempo}  beats {n_beats}  bars {n_bars}  downbeats {len(downbeat_idx)}")
    print(f"  markers: " + ", ".join(f"{k}={v['count']}" for k, v in bars.items()))
    print(f"  sections: {len(sections)}  zones: {[s['zone'] for s in sections]}")
    print(f"  drops: {len(drops)}  at {[round(d['t'],1) for d in drops]}")


if __name__ == "__main__":
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else src.rsplit(".", 1)[0] + ".music.json"
    title = sys.argv[3] if len(sys.argv) > 3 else "awaken"
    main(src, out, title)