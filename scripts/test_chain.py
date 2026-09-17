import subprocess
from pathlib import Path

work = Path(r"X:\chloeos-maestro\songs\silicon_heartbeat\render_work")
ffmpeg = r"X:\ffmpeg\bin\ffmpeg.exe"

fc = (
    "color=black:s=1280x704:r=24:d=1.5,format=yuv420p,settb=1/24[b0];"
    "[0:v]settb=1/24,fps=24[v_in0];"
    "[1:v]settb=1/24,fps=24[v_in1];"
    "[b0][v_in0]xfade=transition=fade:duration=1.5:offset=0[v0];"
    "[v0][v_in1]xfade=transition=dissolve:duration=0.9:offset=7.55[v1]"
)

cmd = [ffmpeg, "-y", "-i", str(work / "seg_001.mp4"), "-i", str(work / "seg_002.mp4"),
       "-filter_complex", fc, "-map", "[v1]", "-t", "10", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(work / "test.mp4")]
r = subprocess.run(cmd, capture_output=True)
print("Return code:", r.returncode)
if r.returncode != 0:
    print(r.stderr.decode("utf-8", "replace"))
else:
    print("Success! Output created.")
