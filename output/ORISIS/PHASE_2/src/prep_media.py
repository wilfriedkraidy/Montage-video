"""Prépare tous les médias de la Phase 2 (sans jamais modifier les sources).

  media/aroll/AROLL_GRADED.mp4  face caméra monté (EDL Phase 1), étalonné et harmonisé entre rushes
  media/audio/VOICE.wav         voix montée, nettoyée
  media/broll/*.mp4             plans B-roll découpés + recadrés (sous-titres / badges retirés)
  media/stills/*.png            illustrations fixes nettoyées et agrandies
Usage : python3 src/prep_media.py   (depuis la racine du dépôt)
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
P2 = os.path.join(REPO, "output", "ORISIS", "PHASE_2")
RUSH = os.path.join(REPO, "media", "source", "ORISIS", "RUSH")
EDL = json.load(open(os.path.join(REPO, "output", "ORISIS", "PHASE_1", "edl.json")))
spec = json.load(open(os.path.join(P2, "src", "data", "timeline.json"), encoding="utf-8"))
M = lambda *p: os.path.join(P2, "media", *p)
for d in ("aroll", "audio", "broll", "stills"):
    os.makedirs(M(d), exist_ok=True)

def run(cmd):
    subprocess.run(cmd, check=True)

def rush_mean(name):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(RUSH, name + ".MP4"), "-vf", "fps=1,scale=90:160",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(float).mean(0)

LOOK = ("eq=contrast=1.07:brightness=-0.012:saturation=1.03,"
        "colorbalance=rs=-0.02:bs=0.035:rm=0.01:bm=-0.01:rh=0.045:gh=0.02:bh=-0.035,"
        "curves=all='0/0.025 0.25/0.225 0.5/0.5 0.75/0.79 1/0.975'")

def aroll():
    out_v, out_a = M("aroll", "AROLL_GRADED.mp4"), M("audio", "VOICE.wav")
    if os.path.exists(out_v) and os.path.exists(out_a) and "-f" not in sys.argv:
        return
    means = {n: rush_mean(n) for n, _ in EDL}
    target = np.mean(list(means.values()), axis=0)
    ins, f, k = [], [], 0
    for i, (name, cuts) in enumerate(EDL):
        ins += ["-i", os.path.join(RUSH, name + ".MP4")]
        g = target / means[name]  # harmonisation colorimétrique entre rushes
        mix = "colorchannelmixer=rr=%.4f:gg=%.4f:bb=%.4f" % tuple(g)
        for a, b in cuts:
            f.append(f"[{i}:v]trim={a}:{b},setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos,setsar=1,fps=30,{mix}[v{k}]")
            d = b - a
            f.append(f"[{i}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"afade=t=in:d=0.02,afade=t=out:st={d-0.03:.3f}:d=0.03[a{k}]")
            k += 1
    f.append("".join(f"[v{n}][a{n}]" for n in range(k)) + f"concat=n={k}:v=1:a=1[cv][ca]")
    f.append(f"[cv]{LOOK},format=yuv420p[ov]")
    f.append("[ca]highpass=f=80,lowpass=f=15000,equalizer=f=3500:t=q:w=1.2:g=1.5,"
             "acompressor=threshold=-24dB:ratio=2.5:attack=10:release=150,"
             "loudnorm=I=-16:TP=-1.5:LRA=8,aresample=48000[oa]")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(f),
         "-map", "[ov]", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-r", "30", out_v,
         "-map", "[oa]", "-c:a", "pcm_s16le", "-ac", "1", out_a])

def broll():
    need = {}
    for s in spec["scenes"]:
        for key in ("clip", "bottom"):
            if key in s and s[key] in spec["clips"]:
                need[s[key]] = s["t1"] - s["t0"]
    H = spec["handle"]
    for cid, dur in need.items():
        c = spec["clips"][cid]
        out = M("broll", cid + ".mp4")
        if os.path.exists(out) and "-f" not in sys.argv:
            continue
        vf = ("crop=1280:548:0:0" if c["crop"] == "scope"
              else "crop=1008:1792:36:128,scale=1080:1920:flags=lanczos")
        run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % max(0, c["t"] - H), "-i", os.path.join(REPO, c["src"]),
             "-t", "%.3f" % (dur + 2 * H), "-vf", vf + ",fps=30,format=yuv420p", "-an",
             "-c:v", "libx264", "-preset", "slow", "-crf", "15", out])

def stills():
    for sid, st in spec["stills"].items():
        out = M("stills", sid + ".png")
        im = Image.open(os.path.join(REPO, st["src"])).convert("RGB")
        l, t, r, b = st["box"]; w, h = im.size
        im = im.crop((int(l * w), int(t * h), int(r * w), int(b * h)))
        m = max(im.size)
        if m < 1600:  # agrandissement doux pour l'usage plein écran
            k = 1600 / m
            im = im.resize((round(im.size[0] * k), round(im.size[1] * k)), Image.LANCZOS)
            im = im.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
        im.save(out)

if __name__ == "__main__":
    stills(); broll(); aroll()
    print("médias prêts")
