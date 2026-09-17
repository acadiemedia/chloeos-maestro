import subprocess
from pathlib import Path

work = Path(r"X:\chloeos-maestro\songs\silicon_heartbeat\render_work")
ffmpeg = r"X:\ffmpeg\bin\ffmpeg.exe"

# Make seg_003 exactly 24.0 - 15.5 = 8.5s long
seg3 = work / "seg_003_fixed.mp4"
vf = "color=c=0x0a1420:s=1280x704:r=24:d=8.5,format=yuv420p"
subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", vf, "-t", "8.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(seg3)], capture_output=True)

fc = (
    "color=black:s=1280x704:r=24:d=1.5,format=yuv420p,settb=1/24[b0];"
    "[0:v]settb=1/24,fps=24[v0_in];"
    "[1:v]settb=1/24,fps=24[v1_in];"
    "[2:v]settb=1/24,fps=24[v2_in];"
    "[b0][v0_in]xfade=transition=fade:duration=1.5:offset=0[v0];"
    "[v0][v1_in]xfade=transition=dissolve:duration=1.0:offset=7.5[v1];"
    "[v1][v2_in]xfade=transition=dissolve:duration=1.0:offset=15.5[v2]"
)

out = work / "test_exact.mp4"
cmd = [ffmpeg, "-y",
       "-i", str(work / "seg_001.mp4"),
       "-i", str(work / "seg_002.mp4"),
       "-i", str(seg3),
       "-filter_complex", fc, "-map", "[v2]",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)]
subprocess.run(cmd, capture_output=True)

probe = [r"X:\ffmpeg\bin\ffprobe.exe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)]
d = subprocess.run(probe, capture_output=True, text=True).stdout.strip()
print(f"Resulting duration: {d} seconds (Target was 24.000000)")
