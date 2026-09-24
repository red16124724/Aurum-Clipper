import os
import subprocess
from pathlib import Path

def generate_sfx():
    out_dir = Path(__file__).parent.parent / "assets" / "sfx"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc=sin(880*2*PI*t)*exp(-5*t):d=1", "-c:a", "libmp3lame", str(out_dir / "ding.mp3")])
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "aevalsrc=random(0)*exp(-3*t)*sin(60*2*PI*t):d=2", "-c:a", "libmp3lame", str(out_dir / "boom.mp3")])
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=pink:d=1.5", "-af", "lowpass=f=1000, volume='exp(-3*abs(t-0.75))':eval=frame", "-c:a", "libmp3lame", str(out_dir / "whoosh.mp3")])
    print("SFX Generated in", out_dir)

if __name__ == "__main__":
    generate_sfx()
