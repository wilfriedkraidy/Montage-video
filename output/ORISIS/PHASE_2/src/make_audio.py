"""OSIRIS – Phase 2 : musique originale, design sonore, ambiances et mixage (synthèse numpy/scipy).

Stems (48 kHz, stéréo, niveaux finaux : MIX = VOICE + MUSIC + SFX) :
  media/audio/VOICE_STEM.wav  voix
  media/audio/MUSIC.wav       musique originale (mode Hijaz en ré) déjà "duckée" sous la voix
  media/audio/SFX.wav         bruitages + ambiances
  media/audio/MIX.wav         mixage final (-14 LUFS, crête -1.5 dBTP)
"""
import json, os, subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile

P2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
A = lambda n: os.path.join(P2, "media", "audio", n)
spec = json.load(open(os.path.join(P2, "src", "data", "timeline.json"), encoding="utf-8"))
SR = 48000
DUR = spec["dur"]
N = int(DUR * SR)
rng = np.random.default_rng(11)

mtof = lambda m: 440.0 * 2 ** ((m - 69) / 12)
def tt(t):
    return np.arange(int(t * SR)) / SR

def add(buf, x, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i >= N or len(x) == 0:
        return
    if i < 0:
        x = x[-i:]; i = 0
    x = x[: N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    if x.ndim == 1:
        buf[i:i + len(x), 0] += x * gain * l * 1.414
        buf[i:i + len(x), 1] += x * gain * r * 1.414
    else:
        buf[i:i + len(x)] += x * gain

def env(n, a, r, sus=1.0):
    e = np.ones(n) * sus
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, sus, na)
    if nr:
        e[n - nr:] *= np.linspace(1, 0, nr)
    return e

def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "low", fs=SR, output="sos"), x, axis=0)
def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x, axis=0)
def bp(x, f1, f2, order=2):
    return signal.sosfilt(signal.butter(order, [f1, f2], "band", fs=SR, output="sos"), x, axis=0)

def saw(f, n, ph=0.0):
    return 2 * ((f * np.arange(n) / SR + ph) % 1.0) - 1

def reverb(x, secs=2.8, wet=0.3, damp=3000):
    n = int(secs * SR)
    ir = rng.normal(0, 1, (n, 2)) * np.exp(-np.arange(n) / (SR * secs / 6.5))[:, None]
    ir = lp(ir, damp); ir /= np.sqrt((ir ** 2).sum(0))
    y = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)
    return x * (1 - wet) + y * wet

# ------------------------------------------------------------------ instruments
def pad(buf, notes, t0, t1, cut=1400, gain=0.05, a=1.2, r=1.6):
    n = int((t1 - t0 + r) * SR)
    for k, m in enumerate(notes):
        f = mtof(m)
        for j, det in enumerate((-0.006, 0.0, 0.006)):
            x = saw(f * (1 + det), n, rng.random())
            x = lp(x, cut) * env(n, a, r)
            add(buf, x, t0, gain / len(notes) ** 0.5, pan=(-0.6, 0.0, 0.6)[j] * 0.8)

def drone(buf, t0, t1, m=38, gain=0.09):
    n = int((t1 - t0) * SR)
    x = lp(saw(mtof(m), n) + 0.6 * saw(mtof(m) * 1.003, n), 380) + 0.8 * np.sin(2 * np.pi * mtof(m - 12) * tt(t1 - t0)[:n])
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.07 * tt(t1 - t0)[:n])
    add(buf, x * env(n, 2.0, 2.0) * lfo, t0, gain)

def ney(buf, m, t0, d, gain=0.06, pan=0.15):
    n = int((d + 0.25) * SR); t = tt(d + 0.25)[:n]
    f = mtof(m)
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.25) * 3, 0, 1)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    x = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    br = bp(rng.normal(0, 1, n), f * 1.5, min(f * 4, 9000)) * 0.5
    add(buf, (x + br) * env(n, 0.14, 0.3), t0, gain, pan)

def pluck(buf, m, t0, d=1.6, gain=0.09, pan=0.0):
    f = mtof(m); P = int(SR / f); n = int(d * SR)
    y = np.zeros(n + P + 1); y[:P] = rng.uniform(-1, 1, P)
    for i in range(P, n, P - 1):                   # Karplus-Strong par blocs
        j = min(P - 1, n - i)
        y[i:i + j] = 0.497 * (y[i - P:i - P + j] + y[i - P + 1:i - P + 1 + j])
    x = lp(y[:n], 3500) * env(n, 0.003, 0.3)
    add(buf, x, t0, gain, pan)

def doum(buf, t0, gain=0.25):
    t = tt(0.6); f = 55 + 40 * np.exp(-t * 18)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) + lp(rng.normal(0, 1, len(t)), 900) * np.exp(-t * 40) * 0.3
    add(buf, x, t0, gain)

def tek(buf, t0, gain=0.07, pan=0.3):
    t = tt(0.08)
    x = hp(rng.normal(0, 1, len(t)), 2500) * np.exp(-t * 70) + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90) * 0.4
    add(buf, x, t0, gain, pan)

# ------------------------------------------------------------------ effets
def impact(buf, t0, gain=0.5):
    t = tt(3.0); f = 26 + 50 * np.exp(-t * 6)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6)
    x += lp(rng.normal(0, 1, len(t)), 400) * np.exp(-t * 6) * 0.5
    x += hp(rng.normal(0, 1, len(t)), 3000) * np.exp(-t * 30) * 0.15
    add(buf, np.tanh(x * 1.4), t0 - 0.02, gain)

def whoosh(buf, tc, d=0.7, gain=0.16, up=True):
    n = int(d * SR); t = np.arange(n) / n
    x = rng.normal(0, 1, n); out = np.zeros(n)
    blk = 512
    for i in range(0, n, blk):                     # passe-bande glissant
        u = t[i]; fc = 300 * (12 ** (u if up else 1 - u))
        out[i:i + blk] = bp(x[i:i + blk + 0], fc * 0.6, min(fc * 1.6, 20000), 1)[: len(out[i:i + blk])]
    e = np.sin(np.pi * t) ** 2
    y = np.stack([out * e * (1 - t), out * e * t], 1) * 1.6
    add(buf, y, tc - d * 0.55, gain)

def swish(buf, t0, gain=0.2):
    n = int(0.28 * SR); t = np.arange(n) / n
    x = bp(rng.normal(0, 1, n), 2500, 9000) * np.sin(np.pi * t) ** 3
    add(buf, x, t0, gain, -0.3)

def chime(buf, t0, gain=0.06, notes=(86, 93, 90, 98)):
    for k, m in enumerate(notes):
        t = tt(2.5); f = mtof(m)
        x = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t)) * np.exp(-t * 2.2)
        add(buf, x * env(len(t), 0.002, 0.2), t0 + k * 0.06, gain, (k - 1.5) * 0.4)

def tok(buf, t0, gain=0.12):
    t = tt(0.15)
    x = np.sin(2 * np.pi * 520 * t) * np.exp(-t * 45) + bp(rng.normal(0, 1, len(t)), 800, 3000) * np.exp(-t * 80) * 0.4
    add(buf, x, t0, gain)

def stamp(buf, t0, gain=0.35):
    t = tt(0.5)
    x = np.sin(2 * np.pi * np.cumsum(70 + 60 * np.exp(-t * 30)) / SR) * np.exp(-t * 12)
    x += bp(rng.normal(0, 1, len(t)), 900, 4500) * np.exp(-t * 35) * 0.6
    add(buf, np.tanh(x * 1.5), t0, gain)

def crumble(buf, t0, d=1.2, gain=0.12):
    for _ in range(70):
        tg = t0 + rng.uniform(0, d) ** 1.6
        n = int(rng.uniform(0.01, 0.05) * SR)
        fc = rng.uniform(400, 3000)
        x = bp(rng.normal(0, 1, n), fc * 0.7, fc * 1.3) * np.exp(-np.arange(n) / n * 5)
        add(buf, x, tg, gain * rng.uniform(0.3, 1.0), rng.uniform(-0.8, 0.8))

def riser(buf, t0, t1, gain=0.12):
    n = int((t1 - t0) * SR); t = np.arange(n) / n
    x = rng.normal(0, 1, n); out = np.zeros(n)
    for i in range(0, n, 1024):
        fc = 200 * 30 ** t[i]
        out[i:i + 1024] = bp(x[i:i + 1024], fc * 0.7, min(fc * 1.4, 20000), 1)
    f = 110 * 4 ** t
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
    add(buf, (out + tone) * t ** 2.2, t0, gain)

def wind(buf, t0, t1, gain=0.05):
    n = int((t1 - t0) * SR)
    x = np.cumsum(rng.normal(0, 1, (n, 2)), 0); x -= lp(x, 5)
    x = bp(x, 150, 900); x /= np.abs(x).max() + 1e-9
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * np.arange(n) / SR + rng.random() * 6)
    add(buf, x * lfo[:, None] * env(n, 1.5, 1.5)[:, None], t0, gain)

def water(buf, t0, t1, gain=0.05):
    n = int((t1 - t0) * SR)
    x = bp(rng.normal(0, 1, (n, 2)), 300, 1600)
    am = np.abs(np.sin(2 * np.pi * 0.7 * np.arange(n) / SR)) ** 3 + 0.25 * np.abs(np.sin(2 * np.pi * 1.9 * np.arange(n) / SR))
    add(buf, x * am[:, None] * env(n, 0.8, 0.8)[:, None], t0, gain)

def scratch(buf, t0, t1, gain=0.03):
    n = int((t1 - t0) * SR)
    x = hp(rng.normal(0, 1, n), 2500) * (0.5 + 0.5 * np.sin(2 * np.pi * 11 * np.arange(n) / SR)) ** 2
    add(buf, x * env(n, 0.1, 0.2), t0, gain)

# ------------------------------------------------------------------ partition
D, Eb, F, Fs, G, A_, Bb, C = 50, 51, 53, 54, 55, 57, 58, 60   # octave 3
CH = {"D": [D, A_, D + 12, Fs + 12], "Dm": [D, A_, D + 12, F + 12], "Eb": [Eb, Bb, Eb + 12, G + 12],
      "Gm": [G - 12, D, G, Bb], "Cm": [C - 12, G - 12, C, Eb + 12], "Bb": [Bb - 12, F, Bb, D + 12],
      "C": [C - 12, G - 12, C, 64], "F": [F - 12, C, F, A_]}
HIJAZ = [62, 63, 66, 67, 69, 70, 72, 74, 75, 78, 79, 81]

def progression(buf, t0, t1, chords, cut=1400, gain=0.05):
    step = (t1 - t0) / len(chords)
    for i, c in enumerate(chords):
        pad(buf, CH[c], t0 + i * step, t0 + (i + 1) * step + 0.4, cut, gain)

def melody(buf, t0, t1, center=4, gain=0.05, seed=1):
    r = np.random.default_rng(seed); t = t0; idx = center
    while t < t1 - 1.0:
        for _ in range(r.integers(3, 6)):
            d = float(r.choice([0.45, 0.7, 0.9, 1.4]))
            idx = int(np.clip(idx + r.choice([-2, -1, -1, 1, 1, 2]), 0, len(HIJAZ) - 1))
            if t + d > t1:
                break
            ney(buf, HIJAZ[idx], t, d * 1.05, gain)
            t += d
        t += float(r.choice([0.8, 1.2, 1.8]))
        idx = center

def groove(buf, t0, t1, bpm=84, dens=1, gain=1.0):
    b = 60 / bpm; t = t0; k = 0
    while t < t1:
        if k % 8 in (0, 3) or (dens > 1 and k % 8 == 6):
            doum(buf, t, 0.22 * gain)
        if k % 8 in (2, 5, 7) or (dens > 1 and k % 2 == 1):
            tek(buf, t, 0.06 * gain, 0.3 if k % 2 else -0.3)
        t += b / 2; k += 1

def arp(buf, t0, t1, chords, gain=0.08, step=0.357):
    seg = (t1 - t0) / len(chords); t = t0; k = 0
    while t < t1:
        c = CH[chords[min(len(chords) - 1, int((t - t0) / seg))]]
        pluck(buf, c[[1, 2, 3, 2][k % 4]] + 12, t, 1.8, gain, ((k % 4) - 1.5) * 0.3)
        t += step; k += 1

def music():
    m = np.zeros((N, 2))
    drone(m, 0, 12.6, 38, 0.08)
    pad(m, [D, A_, Eb + 12], 0.0, 12.3, 900, 0.04)
    progression(m, 12.1, 22.3, ["D", "Eb", "D", "Cm"], 1300, 0.05)
    drone(m, 12.1, 34.5, 38, 0.06)
    pad(m, [Eb, G, Bb, D + 12], 22.26, 26.4, 1800, 0.06)
    progression(m, 26.3, 44.1, ["Gm", "D", "Eb", "D"], 1100, 0.045)
    melody(m, 27.0, 43.5, 4, 0.045, 3)
    progression(m, 44.1, 55.6, ["Bb", "C", "D", "D"], 1700, 0.05)
    riser(m, 52.0, 55.6, 0.05)
    drone(m, 55.6, 90.0, 38, 0.06)
    progression(m, 55.6, 70.0, ["D", "Gm", "Eb", "D"], 1500, 0.05)
    groove(m, 55.6, 69.8, 84, 1, 0.7)
    progression(m, 70.0, 89.9, ["D", "Cm", "Eb", "D"], 1200, 0.045)
    groove(m, 70.0, 89.6, 84, 2, 0.9)
    melody(m, 72.0, 89.0, 5, 0.04, 8)
    progression(m, 89.9, 116.06, ["D", "Eb", "Gm", "Eb", "D", "Eb", "Gm", "Eb"], 1800, 0.055)
    drone(m, 89.9, 116.1, 38, 0.07)
    groove(m, 92.4, 115.8, 92, 2, 1.0)
    riser(m, 110.5, 116.06, 0.10)
    progression(m, 116.06, 132.3, ["Bb", "F", "C", "Dm"], 1000, 0.04)
    arp(m, 117.0, 132.0, ["Bb", "F", "C", "Dm"], 0.05, 0.476)
    progression(m, 132.3, 144.5, ["Gm", "Bb", "F", "D"], 1300, 0.045)
    arp(m, 132.3, 144.3, ["Gm", "Bb", "F", "D"], 0.06, 0.357)
    melody(m, 133.0, 143.8, 6, 0.035, 21)
    pad(m, CH["D"] + [D + 24], 144.4, DUR - 0.2, 1600, 0.07, a=0.3, r=2.4)
    drone(m, 144.4, DUR, 38, 0.07)
    m[int(116.0 * SR):int(116.06 * SR)] *= np.linspace(1, 0.2, int(0.06 * SR))[:, None]
    return reverb(m, 3.2, 0.32)

def sfx():
    s = np.zeros((N, 2))
    sc = spec["scenes"]
    for a, b in zip(sc, sc[1:]):
        if not (a["kind"] == "A" and b["kind"] == "A"):
            whoosh(s, b["t0"], 0.7, 0.10 if "A" in (a["kind"], b["kind"]) else 0.08, up=b["kind"] != "A")
    for t in (12.10, 70.02, 89.88, 116.06):
        impact(s, t, 0.42)
    impact(s, 144.6, 0.5)
    swish(s, 22.35, 0.22); impact(s, 22.30, 0.22)
    impact(s, 24.45, 0.3); crumble(s, 24.45, 1.3, 0.14)
    for t in (119.10, 131.00):
        stamp(s, t + 0.14, 0.4)
    for e in spec["texts"]:
        if e["style"] == "hero":
            chime(s, e["t0"], 0.035)
        if e["style"] == "tag":
            tok(s, e["t0"], 0.04)
    for t in (80.35, 81.30, 82.22):
        tok(s, t, 0.14); chime(s, t, 0.02, (86,))
    scratch(s, 96.3, 99.2, 0.025)
    for t in (96.0, 99.1):
        chime(s, t, 0.03, (93, 98))
    for t in (22.26, 95.50, 135.08):
        crumble(s, t - 0.1, 0.4, 0.05)
    # ambiances
    for t0, t1 in ((0, 3.6), (12.0, 26.4), (30.3, 34.3), (44.0, 55.7), (58.7, 72.6), (76.3, 80.3), (86.3, 92.5), (95.4, 116.1),
                   (123.8, 128.1), (135.0, 140.0), (142.2, DUR)):
        wind(s, t0, t1, 0.035)
    water(s, 26.2, 30.5, 0.05)
    return reverb(s, 1.8, 0.18)

# ------------------------------------------------------------------ mix
def lufs(x):
    tmp = A("_tmp.wav"); wavfile.write(tmp, SR, x.astype(np.float32))
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    os.remove(tmp)
    return float(out.split("Integrated loudness:")[1].split("I:")[1].split("LUFS")[0])

def main():
    sr, v = wavfile.read(A("VOICE.wav"))
    v = v.astype(np.float64) / 32768.0
    voice = np.zeros((N, 2)); voice[: len(v)] = v[:N, None]
    mus, fx = music(), sfx()
    # ducking : enveloppe de la voix (attaque 60 ms, relâche 450 ms)
    e = np.sqrt(signal.sosfilt(signal.butter(1, 8, "low", fs=SR, output="sos"), v ** 2))
    e = np.clip(e / (np.percentile(e, 95) + 1e-9), 0, 1)
    g = np.zeros_like(e); att, rel = np.exp(-1 / (0.06 * SR)), np.exp(-1 / (0.45 * SR)); acc = 0.0
    sub = 64
    for i in range(0, len(e), sub):
        x = e[i:i + sub].max(); c = att if x > acc else rel
        acc = c ** sub * acc + (1 - c ** sub) * x; g[i:i + sub] = acc
    duck = np.ones(N); duck[: len(g)] = 1 - 0.62 * np.clip(g * 1.6, 0, 1)
    mus *= duck[:, None]
    mus *= 10 ** ((-25.5 - lufs(mus)) / 20)
    fx *= 10 ** ((-26.0 - lufs(fx)) / 20)
    voice *= 10 ** ((-16.5 - lufs(voice)) / 20)
    mix = voice + mus + fx
    k = 10 ** ((-14.0 - lufs(mix)) / 20)
    stems = {"VOICE_STEM.wav": voice * k, "MUSIC.wav": mus * k, "SFX.wav": fx * k}
    mix = sum(stems.values())
    lim = 10 ** (-1.6 / 20)                          # limiteur doux (crêtes)
    over = np.abs(mix) > lim * 0.8
    mix = np.where(over, np.sign(mix) * (lim * 0.8 + (lim * 0.2) * np.tanh((np.abs(mix) - lim * 0.8) / (lim * 0.2))), mix)
    for n, x in list(stems.items()) + [("MIX.wav", mix)]:
        if n == "VOICE_STEM.wav":
            x = x[:, 0]                              # voix mono (identique sur les deux canaux)
        wavfile.write(A(n), SR, (np.clip(x, -1, 1) * 32767).astype(np.int16))
    print("mix LUFS ≈", round(lufs(mix), 2), "| peak dBFS", round(20 * np.log10(np.abs(mix).max()), 2))

if __name__ == "__main__":
    main()
