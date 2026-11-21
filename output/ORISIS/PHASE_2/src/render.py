"""OSIRIS – Phase 2 : moteur de rendu du motion design (Python + FFmpeg).

Lit src/data/timeline.json et compose image par image :
  A-roll étalonné, B-roll en plans 2.5D (projection caméra identique à AE, zoom = CAM_ZOOM),
  graphismes animés, titres, sous-titres karaoké, éclairs, grain, vignettage (sans particules).
Usage : python3 src/render.py OUT.mp4 [--workers 4] [--from s --to s] [--still t1,t2,...]
"""
import json, math, os, subprocess, sys, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

P2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
spec = json.load(open(os.path.join(P2, "src", "data", "timeline.json"), encoding="utf-8"))
W, H, FPS, DUR = spec["w"], spec["h"], spec["fps"], spec["dur"]
TR, HANDLE, ZOOM = spec["tr"], spec["handle"], spec["cam_zoom"]
MED = lambda *p: os.path.join(P2, "media", *p)
DATA = lambda n: json.load(open(os.path.join(P2, "src", "data", n)))
FONT = functools.lru_cache(None)(lambda n, s: ImageFont.truetype(MED("fonts", n + ".ttf"), s))
GOLD, GOLD_L, CREAM, RED = (226, 184, 98), (250, 222, 150), (243, 233, 210), (196, 38, 44)

# ------------------------------------------------------------------ outils
clamp = lambda x, a=0.0, b=1.0: max(a, min(b, x))
lerp = lambda a, b, u: a + (b - a) * u
def ease(u):      # easy ease (AE, influence 33 %) ~ smoothstep
    u = clamp(u); return u * u * (3 - 2 * u)
def ease_out(u):
    u = clamp(u); return 1 - (1 - u) ** 3
def back_out(u, s=1.6):
    u = clamp(u) - 1; return 1 + (s + 1) * u ** 3 + s * u ** 2

def paste(base, im, x, y, op=1.0):
    """alpha-composite im (RGBA) sur base (RGBA) en (x,y) coin haut-gauche, avec opacité."""
    if op <= 0.003 or im is None:
        return
    x, y = int(round(x)), int(round(y))
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, base.width - x), min(im.height, base.height - y)
    if r <= l or b <= t:
        return
    src = im.crop((l, t, r, b)) if (l or t or r < im.width or b < im.height) else im
    if op < 0.997:
        src = src.copy(); a = src.getchannel("A").point(lambda v: int(v * op)); src.putalpha(a)
    base.alpha_composite(src, (x + l, y + t))

def cover(im, w, h):
    k = max(w / im.width, h / im.height)
    im = im.resize((max(w, round(im.width * k)), max(h, round(im.height * k))), Image.BILINEAR)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))

def zoom_frame(im, s, ax=W / 2, ay=H / 2):
    if abs(s - 1) < 1e-4:
        return im
    return im.transform((W, H), Image.AFFINE, (1 / s, 0, ax - ax / s, 0, 1 / s, ay - ay / s), Image.BICUBIC)

def blur_bg(im, dark=0.5, radius=6):
    sm = cover(im.convert("RGB"), 216, 384).filter(ImageFilter.GaussianBlur(radius))
    sm = Image.eval(sm, lambda v: int(v * dark))
    return sm.resize((W, H), Image.BICUBIC).convert("RGBA")

# ------------------------------------------------------------------ projection 2.5D (caméra AE)
def project(pts, pos, rx, ry, scale, anchor):
    out = []
    crx, srx, cry, sry = math.cos(math.radians(rx)), math.sin(math.radians(rx)), math.cos(math.radians(ry)), math.sin(math.radians(ry))
    for u, v in pts:
        x, y, z = (u - anchor[0]) * scale, (v - anchor[1]) * scale, 0.0
        y, z = y * crx - z * srx, y * srx + z * crx
        x, z = x * cry + z * sry, -x * sry + z * cry
        X, Y, Z = pos[0] + x, pos[1] + y, pos[2] + z
        k = ZOOM / (ZOOM + Z)
        out.append((W / 2 + (X - W / 2) * k, H / 2 + (Y - H / 2) * k))
    return out

def persp_coeffs(dst, src):
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

def draw_3d(base, im, pos, rx=0, ry=0, scale=1.0, anchor=None, op=1.0):
    """dessine le calque im (RGBA) comme un calque 3D AE (position, rotations X/Y, échelle, point d'ancrage)."""
    if anchor is None:
        anchor = (im.width / 2, im.height / 2)
    src = [(0, 0), (im.width, 0), (im.width, im.height), (0, im.height)]
    dst = project(src, pos, rx, ry, scale, anchor)
    xs, ys = [p[0] for p in dst], [p[1] for p in dst]
    x0, y0 = max(-50, int(min(xs)) - 1), max(-50, int(min(ys)) - 1)
    x1, y1 = min(W + 50, int(max(xs)) + 2), min(H + 50, int(max(ys)) + 2)
    if x1 <= x0 or y1 <= y0:
        return
    c = persp_coeffs([(x - x0, y - y0) for x, y in dst], src)
    out = im.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, c, Image.BICUBIC, fillcolor=(0, 0, 0, 0))
    paste(base, out, x0, y0, op)

# ------------------------------------------------------------------ lecture vidéo séquentielle
class Reader:
    def __init__(self, path, w, h):
        self.path, self.w, self.h, self.p, self.idx, self.last = path, w, h, None, None, None
    def _open(self, t):
        if self.p:
            self.p.kill()
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", "%.4f" % max(0, t), "-i", self.path, "-f", "rawvideo",
                                   "-pix_fmt", "rgb24", "-s", f"{self.w}x{self.h}", "-"], stdout=subprocess.PIPE, bufsize=10 ** 8)
        self.t0 = max(0, t); self.idx = -1
    def get(self, t):
        k = round((t - (self.t0 if self.p else 0)) * FPS) if self.p else None
        if self.p is None or k is None or k < self.idx or k > self.idx + 90:
            self._open(t); k = 0
        while self.idx < k:
            raw = self.p.stdout.read(self.w * self.h * 3)
            if len(raw) < self.w * self.h * 3:
                break
            self.last = raw; self.idx += 1
        return Image.frombuffer("RGB", (self.w, self.h), self.last, "raw", "RGB", 0, 1)
    def close(self):
        if self.p:
            self.p.kill(); self.p = None

READERS = {}
def reader(path, w, h):
    if path not in READERS:
        READERS[path] = Reader(path, w, h)
    return READERS[path]

# ------------------------------------------------------------------ ressources statiques
@functools.lru_cache(None)
def img(name):
    return Image.open(MED(*name.split("/"))).convert("RGBA")

def ensure_assets():
    """Assets partagés avec After Effects (cartes encadrées, ornements, symboles)."""
    g = lambda n: MED("graphics", n)
    # cartes encadrées (illustration + filet or + ombre)
    for sid in spec["stills"]:
        out = g("CARD_" + sid + ".png")
        if os.path.exists(out):
            continue
        im = Image.open(MED("stills", sid + ".png")).convert("RGB")
        im.thumbnail((880, 880), Image.LANCZOS)
        framed(im).save(out)
    for sid, box in (("ST_BLACK_CHRIST", None),):
        out = g("SPLIT_" + sid + ".png")
        if not os.path.exists(out):
            im = Image.open(MED("stills", sid + ".png")).convert("RGB")
            w = im.width; h = int(w * 560 / 860)
            im = im.crop((0, int(im.height * 0.02), w, int(im.height * 0.02) + h)).resize((860, 560), Image.LANCZOS)
            framed(im).save(out)
    if not os.path.exists(g("PLATE_ORNAMENT.png")):
        o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(o)
        for y in (960 - 290, 960 + 290):
            for x0, x1 in ((130, 500), (580, 950)):
                d.line([(x0, y), (x1, y)], fill=GOLD + (200,), width=2)
            d.polygon([(540, y - 9), (549, y), (540, y + 9), (531, y)], outline=GOLD_L + (255,), fill=GOLD + (120,))
        o.save(g("PLATE_ORNAMENT.png"))
    if not os.path.exists(g("SYMBOL_EQ.png")):
        for name, slash in (("SYMBOL_EQ.png", False), ("SYMBOL_NEQ.png", True)):
            k = 4; s = Image.new("L", (220 * k, 160 * k), 0); d = ImageDraw.Draw(s)
            d.rounded_rectangle([40 * k, 50 * k, 180 * k, 66 * k], 8 * k, fill=255)
            d.rounded_rectangle([40 * k, 94 * k, 180 * k, 110 * k], 8 * k, fill=255)
            if slash:
                d.line([(140 * k, 20 * k), (80 * k, 140 * k)], fill=255, width=14 * k)
            s = s.resize((220, 160), Image.LANCZOS)
            im = Image.new("RGBA", s.size, GOLD_L + (0,)); im.putalpha(s)
            gl = Image.new("RGBA", s.size, GOLD + (0,)); gl.putalpha(s.filter(ImageFilter.GaussianBlur(8)))
            Image.alpha_composite(gl, im).save(g(name))

def framed(im, border=3, pad=60):
    w, h = im.size
    card = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", card.size, 0); ImageDraw.Draw(sh).rectangle([pad, pad + 14, pad + w, pad + h + 14], fill=190)
    card.putalpha(sh.filter(ImageFilter.GaussianBlur(22)))
    inner = im.convert("RGBA"); d = ImageDraw.Draw(inner)
    d.rectangle([0, 0, w - 1, h - 1], outline=GOLD + (255,), width=border)
    d.rectangle([border + 5, border + 5, w - border - 6, h - border - 6], outline=GOLD_L + (110,), width=1)
    card.alpha_composite(inner, (pad, pad))
    return card

# ------------------------------------------------------------------ texte
def text_img(s, font, size, fill, track=0, stroke=0, stroke_fill=None, glow=None, shadow=0.55):
    f = FONT(font, size)
    widths = [f.getlength(c) for c in s]
    tw = sum(widths) + track * max(0, len(s) - 1)
    asc, desc = f.getmetrics()
    pad = 40 + stroke
    im = Image.new("RGBA", (int(tw) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    m = Image.new("L", im.size, 0); dm = ImageDraw.Draw(m)
    x = pad
    for c, cw in zip(s, widths):
        dm.text((x, pad), c, font=f, fill=255, stroke_width=stroke); x += cw + track
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(m.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * shadow)))
        im.alpha_composite(sh, (0, 6))
    if glow:
        gl = Image.new("RGBA", im.size, glow + (0,)); gl.putalpha(m.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(min(255, v * 0.9))))
        im.alpha_composite(gl)
    if stroke:
        st = Image.new("RGBA", im.size, stroke_fill + (0,)); st.putalpha(m); im.alpha_composite(st)
        m = Image.new("L", im.size, 0); dm = ImageDraw.Draw(m); x = pad
        for c, cw in zip(s, widths):
            dm.text((x, pad), c, font=f, fill=255); x += cw + track
    fl = Image.new("RGBA", im.size, fill + (0,)); fl.putalpha(m); im.alpha_composite(fl)
    return im

def fit(s, font, size, maxw, track=0):
    while size > 20 and FONT(font, size).getlength(s) + track * len(s) > maxw:
        size -= 4
    return size

@functools.lru_cache(maxsize=512)
def hero_img(s, track, sub):
    size = fit(s, "Cinzel-Black", 150, 960, track)
    return text_img(s, "Cinzel-Black", size, GOLD_L, track, glow=GOLD) if not sub else \
        text_img(s, "Cinzel-Bold", 62, CREAM, track + 6, glow=None)

@functools.lru_cache(maxsize=512)
def simple_img(s, font, size, fill, track, glow=None):
    return text_img(s, font, size, fill, track, glow=glow)

def draw_text_event(base, e, t):
    st, a, b = e["style"], e["t0"], e["t1"]
    u_in, u_out = (t - a), (b - t)
    if u_in < 0 or u_out < 0:
        return
    if st == "hero":
        k = ease_out(u_in / 0.55); o = min(k, ease(u_out / 0.35))
        tr = int(lerp(34, 6, k)); sc = lerp(1.16, 1.0, k) * lerp(1.0, 0.97, 1 - ease(u_out / 0.35))
        y = e["y"] or 300
        im = hero_img(e["text"], tr, False)
        if abs(sc - 1) > 0.003:
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
        paste(base, im, W / 2 - im.width / 2, y - im.height / 2, o)
        if e["sub"]:
            k2 = ease_out((u_in - 0.18) / 0.55); sim = hero_img(e["sub"], int(lerp(30, 8, k2)), True)
            paste(base, sim, W / 2 - sim.width / 2, y + 122 - sim.height / 2 + 20 * (1 - k2), min(k2, o))
    elif st == "chapter":
        k = ease_out(u_in / 0.6); o = min(ease(u_in / 0.35), ease(u_out / 0.4))
        y = e["y"] or 900
        shade = Image.new("RGBA", (W, H), (0, 0, 0, int(105 * o))) if not e["y"] else None
        if shade:
            base.alpha_composite(shade)
        sub = simple_img(e["sub"], "Cinzel-Bold", 44, GOLD, 18)
        paste(base, sub, W / 2 - sub.width / 2, y - 95 - sub.height / 2, o)
        d = ImageDraw.Draw(base); L = 150 * k; hw = sub.width / 2 - 30
        col = GOLD + (int(220 * o),)
        d.line([(W / 2 - hw - 20 - L, y - 95 + 4), (W / 2 - hw - 20, y - 95 + 4)], fill=col, width=2)
        d.line([(W / 2 + hw + 20, y - 95 + 4), (W / 2 + hw + 20 + L, y - 95 + 4)], fill=col, width=2)
        size = fit(e["text"], "Cinzel-Black", 96, 980, 4)
        tr = int(lerp(26, 4, k))
        ti = simple_img(e["text"], "Cinzel-Black", size, CREAM, tr, GOLD)
        paste(base, ti, W / 2 - ti.width / 2, y + 10 - ti.height / 2, o)
    elif st == "tag":
        k = ease_out(u_in / 0.4); o = min(k, ease(u_out / 0.3))
        y = (e["y"] or 1330) + 26 * (1 - k)
        ti = simple_img(e["text"], "Cinzel-Bold", fit(e["text"], "Cinzel-Bold", 46, 900, 6), GOLD_L, 6)
        bw, bh = ti.width - 20, 88
        band = Image.new("RGBA", (bw, bh), (8, 5, 2, 150)); d = ImageDraw.Draw(band)
        d.line([(0, 0), (bw, 0)], fill=GOLD + (230,), width=2); d.line([(0, bh - 1), (bw, bh - 1)], fill=GOLD + (230,), width=2)
        paste(base, band, W / 2 - bw / 2, y - bh / 2, o * 0.95)
        paste(base, ti, W / 2 - ti.width / 2, y - ti.height / 2 + 2, o)
    elif st == "stamp":
        k = clamp(u_in / 0.16); o = min(k, ease(u_out / 0.3))
        sc = lerp(1.8, 1.0, k ** 2)
        im = stamp_img(e["text"])
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
        paste(base, im, W / 2 - im.width / 2, (e["y"] or 1150) - im.height / 2, o)
    elif st == "end":
        k = ease_out(u_in / 1.2); o = ease(u_in / 0.8) * ease(u_out / 0.6 + 0.3)
        ti = simple_img(e["text"], "Cinzel-Black", 200, GOLD_L, int(lerp(70, 24, k)), GOLD)
        paste(base, ti, W / 2 - ti.width / 2, 860 - ti.height / 2, o)
        k2 = ease_out((u_in - 0.4) / 1.0)
        sub = simple_img(e["sub"], "Cinzel-Bold", 44, CREAM, 14)
        paste(base, sub, W / 2 - sub.width / 2, 1010 - sub.height / 2, min(o, k2))

@functools.lru_cache(None)
def stamp_img(s):
    ti = text_img(s, "Cinzel-Black", fit(s, "Cinzel-Black", 84, 820, 4), RED, 4, shadow=0)
    w, h = ti.width - 20, 150
    box = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(box)
    d.rectangle([20, 20, 20 + w, 20 + h], outline=RED + (255,), width=9)
    d.rectangle([34, 34, 6 + w, 6 + h], outline=RED + (160,), width=2)
    box.alpha_composite(ti, (box.width // 2 - ti.width // 2, box.height // 2 - ti.height // 2))
    rng = np.random.default_rng(3)   # texture tampon usé
    a = np.array(box.getchannel("A"), float) * (0.75 + 0.25 * rng.random((box.height, box.width)))
    box.putalpha(Image.fromarray(a.astype(np.uint8)))
    return box.rotate(7, Image.BICUBIC, expand=True)

# ------------------------------------------------------------------ sous-titres karaoké
CAP = spec["captions"]
CAP_Y = 1560

@functools.lru_cache(maxsize=256)
def caption_img(ci, wi):
    words = CAP[ci]["words"]
    f = FONT("Montserrat-ExtraBold", 60)
    space = f.getlength(" ")
    lines, cur, cw = [], [], 0
    for i, w in enumerate(words):
        lw = f.getlength(w["w"])
        if cur and cw + space + lw > 940:
            lines.append(cur); cur, cw = [], 0
        cur.append(i); cw += (space if cw else 0) + lw
    lines.append(cur)
    lh = 76
    im = Image.new("RGBA", (W, lh * len(lines) + 60), (0, 0, 0, 0))
    m_all = Image.new("L", im.size, 0); m_hi = Image.new("L", im.size, 0)
    da, dh = ImageDraw.Draw(m_all), ImageDraw.Draw(m_hi)
    for li, line in enumerate(lines):
        tw = sum(f.getlength(words[i]["w"]) for i in line) + space * (len(line) - 1)
        x = W / 2 - tw / 2; y = 30 + li * lh
        for i in line:
            (dh if i == wi else da).text((x, y), words[i]["w"], font=f, fill=255)
            x += f.getlength(words[i]["w"]) + space
    both = Image.fromarray(np.maximum(np.array(m_all), np.array(m_hi)))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(both.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.8)))
    im.alpha_composite(sh, (0, 4))
    st = Image.new("RGBA", im.size, (18, 12, 6, 0)); st.putalpha(both.filter(ImageFilter.MaxFilter(9)))
    im.alpha_composite(st)
    wh = Image.new("RGBA", im.size, (255, 255, 255, 0)); wh.putalpha(m_all); im.alpha_composite(wh)
    hi = Image.new("RGBA", im.size, (245, 196, 81, 0)); hi.putalpha(m_hi); im.alpha_composite(hi)
    return im

def draw_captions(base, t):
    for ci, c in enumerate(CAP):
        nxt = CAP[ci + 1]["start"] if ci + 1 < len(CAP) else c["end"] + 0.6
        a, b = c["start"] - 0.04, min(c["end"] + 0.35, nxt - 0.02)
        if a <= t < b:
            wi = -1
            for i, w in enumerate(c["words"]):
                if t >= w["s"] - 0.02:
                    wi = i
            im = caption_img(ci, wi)
            k = clamp((t - a) / 0.1); sc = lerp(0.93, 1.0, ease_out(k))
            if sc < 0.999:
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
            paste(base, im, W / 2 - im.width / 2, CAP_Y - im.height / 2, min(1.0, k * 1.5))
            return

# ------------------------------------------------------------------ scènes
AROLL = MED("aroll", "AROLL_GRADED.mp4")
EG = DATA("egypt_pieces.json"); RT = DATA("route.json"); AF = DATA("africa.json"); MG = DATA("magnifier.json")

def clip_frame(cid, t_local):
    c = spec["clips"][cid]
    w, h = (1280, 548) if c["crop"] == "scope" else (1080, 1920)
    return reader(MED("broll", cid + ".mp4"), w, h).get(t_local + HANDLE)

@functools.lru_cache(maxsize=64)
def bg_still(sid):
    return blur_bg(Image.open(MED("stills", sid + ".png")), 0.42, 7)

def scene_frame(s, t, extra):
    """rend la scène s à l'instant t (global). extra = sur-zoom de transition."""
    d = s["t1"] - s["t0"]; u = (t - s["t0"]) / d; tl = t - s["t0"]
    k = s["kind"]
    if k == "A":
        fr = reader(AROLL, W, H).get(min(t, spec["voice_dur"] - 0.04)).convert("RGBA")
        return zoom_frame(fr, lerp(*s["s"], u) * extra, W / 2, 760)
    if k == "FULL":
        fr = clip_frame(s["clip"], tl).convert("RGBA")
        out = zoom_frame(fr, lerp(*s["s"], u) * extra)
        if s.get("end"):
            dk = ease((t - 144.4) / 1.2) * 0.62
            if dk > 0:
                out.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * dk))))
        return out
    base = None
    if k == "PLATE":
        fr = clip_frame(s["clip"], tl)
        base = zoom_frame(blur_bg(fr, 0.40, 6), lerp(1.12, 1.2, u))
        pl = framed(fr.resize((1060, 454), Image.BICUBIC), border=2, pad=50)
        draw_3d(base, pl, (W / 2, 960, lerp(*s["z"], ease(u))), 0, lerp(*s["ry"], ease(u)), extra)
        paste(base, img("graphics/PLATE_ORNAMENT.png"), 0, 0, ease(tl / 0.6))
        return base
    if k == "CARD":
        base = zoom_frame(bg_still(s["img"]).copy(), lerp(1.1, 1.22, u))
        card = img("graphics/CARD_" + s["img"] + ".png")
        draw_3d(base, card, (W / 2, 960, lerp(*s["z"], ease(u))), lerp(*s["rx"], ease(u)), lerp(*s["ry"], ease(u)), extra)
        return base
    base = zoom_frame(img("graphics/PAPYRUS_BG.png").copy(), lerp(1.0, 1.06, u) * extra)
    if k == "SPLIT":
        sep = ease_out(tl / 0.7) * 50 if s.get("split") else 0
        kin = ease_out(tl / 0.6)
        top = img("graphics/SPLIT_" + s["top"] + ".png")
        fr = clip_frame(s["bottom"], tl)
        bot = framed(cover(fr, 860, 560), 3, 60)
        draw_3d(base, top, (W / 2 - 60 * (1 - kin), 470 - sep, lerp(80, -30, u)), 0, lerp(-9, -3, u), extra, op=kin)
        draw_3d(base, bot, (W / 2 + 60 * (1 - kin), 1200 + sep, lerp(80, -30, u)), 0, lerp(9, 3, u), extra, op=kin)
        for (lab, y) in zip(s["labels"], (705 - sep, 1432 + sep)):
            li = simple_img(lab, "Cinzel-Black", 58, GOLD_L, 8, GOLD)
            paste(base, li, W / 2 - li.width / 2, y - li.height / 2, kin)
        sym = img("graphics/SYMBOL_NEQ.png" if s.get("split") else "graphics/SYMBOL_EQ.png")
        ks = back_out((tl - 0.35) / 0.4) if tl > 0.35 else 0
        if ks > 0.01:
            si = sym.resize((max(1, int(sym.width * ks * 0.8)), max(1, int(sym.height * ks * 0.8))), Image.BICUBIC)
            paste(base, si, W / 2 - si.width / 2, 836 - si.height / 2, clamp(ks))
        if not s.get("split"):
            q = simple_img("?", "Cinzel-Black", 90, GOLD_L, 0, GOLD)
            paste(base, q, W / 2 + 70 - q.width / 2, 836 - q.height / 2, clamp((tl - 0.6) / 0.3))
        return base
    if k == "MAP_EGYPT":
        sh = s["shatter"] - s["t0"]
        zc = lerp(220, -60, ease(u)); rx = lerp(18, 8, ease(u))
        size = EG["size"]
        if tl < sh:
            draw_3d(base, img("graphics/EGYPT_MAP.png"), (W / 2, 900, zc), rx, 0, 1.0)
            lab = simple_img("ÉGYPTE", "Cinzel-Black", 84, CREAM, 18, GOLD)
            paste(base, lab, W / 2 - lab.width / 2, 300 - lab.height / 2, ease(tl / 0.5) * ease((sh - tl) / 0.25))
        else:
            for p in EG["pieces"]:
                q = ease_out((tl - sh - p["delay"]) / 1.1)
                tx, ty = p["x"] * 0.55 + p["corner"][0] * 270, p["y"] * 0.55 + p["corner"][1] * 520
                x = lerp(p["x"], tx, q); y = lerp(p["y"], ty, q)
                pim = img("graphics/" + p["file"])
                if q > 0.002:
                    pim = pim.rotate(-p["rot"] * q, Image.BICUBIC, expand=True)
                    sc = lerp(1.0, 0.62, q)
                    pim = pim.resize((max(1, int(pim.width * sc)), max(1, int(pim.height * sc))), Image.BICUBIC)
                # fragment placé dans le plan 3D de la carte (même projection)
                cx, cy = project([(size / 2 + x, size / 2 + y)], (W / 2, 900, zc), rx, 0, 1.0, (size / 2, size / 2))[0]
                kz = ZOOM / (ZOOM + zc)
                pim = pim.resize((max(1, int(pim.width * kz)), max(1, int(pim.height * kz))), Image.BICUBIC)
                paste(base, pim, cx - pim.width / 2, cy - pim.height / 2, lerp(1, 0.9, q))
        return base
    if k == "ICONS":
        names = (("ICON_PAIN", "PAIN"), ("ICON_BIERE", "BIÈRE"), ("ICON_VIN", "VIN"))
        d = ImageDraw.Draw(base)
        L = ease_out(tl / 0.8) * 420
        d.line([(W / 2 - L, 1060), (W / 2 + L, 1060)], fill=GOLD + (170,), width=2)
        for i, ((icn, lab), at) in enumerate(zip(names, s["at"])):
            q = (t - at) / 0.45
            if q <= 0:
                continue
            sc = back_out(q) * 0.72
            im = img("graphics/" + icn + ".png")
            im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BICUBIC)
            x = 200 + 340 * i
            paste(base, im, x - im.width / 2, 880 - im.height / 2, clamp(q * 1.5))
            li = simple_img(lab, "Cinzel-Black", 54, GOLD_L, 10, GOLD)
            paste(base, li, x - li.width / 2, 1130 - li.height / 2 + 20 * (1 - ease_out(q)), clamp(q * 1.5))
        return base
    if k == "MAP_ROUTE":
        S = RT["size"]; plane = img("graphics/ROUTE_MAP.png").copy()
        p = ease((t - s["draw"][0]) / (s["draw"][1] - s["draw"][0]))
        x0, x1 = RT["cairo"][0] - 12, RT["jeru"][0] + 12
        if p > 0:
            ln = img("graphics/ROUTE_LINE.png")
            xr = int(lerp(x0, x1, p))
            ln = ln.crop((0, 0, max(1, xr), S)); plane.alpha_composite(ln)
        dd = ImageDraw.Draw(plane)
        for (pt, lab, at) in ((RT["cairo"], "ÉGYPTE", s["draw"][0] - 0.3), (RT["jeru"], "ISRAËL", s["draw"][1] - 0.1)):
            q = clamp((t - at) / 0.4)
            if q <= 0:
                continue
            pulse = 1 + 0.25 * math.sin((t - at) * 6)
            r = 14 * back_out(q) * pulse
            dd.ellipse([pt[0] - r * 2.2, pt[1] - r * 2.2, pt[0] + r * 2.2, pt[1] + r * 2.2], outline=GOLD_L + (int(120 * q),), width=3)
            dd.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=(255, 236, 180, int(255 * q)))
            li = simple_img(lab, "Cinzel-Black", 64, GOLD_L, 8, GOLD)
            paste(plane, li, pt[0] - li.width / 2 + (0 if lab == "ÉGYPTE" else 40), pt[1] + (60 if lab == "ÉGYPTE" else -110) - li.height / 2, q)
        mid = ((RT["cairo"][0] + RT["jeru"][0]) / 2, (RT["cairo"][1] + RT["jeru"][1]) / 2)
        draw_3d(base, plane, (W / 2, 880, lerp(500, 60, ease_out(u * 1.2))), lerp(32, 22, u), lerp(-6, 4, u), 1.0 * extra, mid)
        cap = simple_img("LE CULTE D'OSIRIS VOYAGE", "Cinzel-Bold", 44, CREAM, 8)
        paste(base, cap, W / 2 - cap.width / 2, 330 - cap.height / 2, ease((tl - 0.5) / 0.5) * ease((d - tl) / 0.4))
        return base
    if k == "AFRICA":
        af = img("graphics/AFRICA.png"); aw, ah = AF["size"]
        pos = (W / 2, 1000, lerp(260, 0, ease(u))); rx, ry = lerp(14, 6, u), lerp(-12, 8, ease(u))
        draw_3d(base, af, pos, rx, ry, 0.82 * extra)
        ex, ey = project([tuple(AF["egypt"])], pos, rx, ry, 0.82 * extra, (aw / 2, ah / 2))[0]
        q = ease((tl - 0.3) / 2.6)
        mx, my = lerp(180, ex, q), lerp(1500, ey, q)
        mg = img("graphics/MAGNIFIER.png"); lx, ly = MG["lens"]
        paste(base, mg, mx - lx, my - ly, ease(tl / 0.5))
        return base
    raise ValueError(k)

# ------------------------------------------------------------------ post (éclairs, grain, fondus)
GRAIN = [np.asarray(Image.fromarray(np.random.default_rng(i).normal(128, 40, (H // 2, W // 2)).clip(0, 255).astype(np.uint8))
                    .resize((W, H), Image.BILINEAR), np.float32)[..., None] * (3.2 / 40) - 128 * (3.2 / 40) for i in range(6)]
YY, XX = np.mgrid[0:H, 0:W]
FLASH = (np.clip(1 - np.sqrt(((XX - W * 0.62) / 900.0) ** 2 + ((YY - H * 0.36) / 1200.0) ** 2), 0, 1) ** 1.8)[..., None] * \
    np.array([255, 178, 96], np.float32)
del YY, XX

def post(frame_rgba, t, fi, part):
    f = np.asarray(frame_rgba.convert("RGB"), np.float32)
    fl = 0.0
    for tf in spec["flashes"]:
        dt = t - tf
        if -0.15 < dt < 0.5:
            fl = max(fl, (1 - abs(dt) / 0.15) if dt < 0 else (1 - dt / 0.5) ** 1.5)
    if fl > 0:
        f = f + FLASH * (0.55 * fl)
    f = f + GRAIN[(fi // 2) % 6]   # grain argentique doux, renouvelé toutes les 2 images
    fade = min(1.0, t / 0.4, (DUR - t) / 0.9)
    if fade < 1:
        f = f * max(0.0, fade)
    return np.clip(f, 0, 255).astype(np.uint8)

VIG = None
def render_frame(t, fi, part):
    global VIG
    if VIG is None:
        VIG = img("graphics/VIGNETTE.png")
    sc = spec["scenes"]; base = None
    for i, s in enumerate(sc):
        a0 = s["t0"] - (TR / 2 if i else 0); a1 = s["t1"] + (TR / 2 if i < len(sc) - 1 else 0)
        if not (a0 <= t < a1):
            continue
        a_in = 1.0 if i == 0 else ease((t - a0) / TR)
        nxt = ease((t - (s["t1"] - TR / 2)) / TR) if i < len(sc) - 1 else 0
        extra = lerp(1.05, 1.0, a_in) * lerp(1.0, 1.05, nxt)
        fr = scene_frame(s, t, extra)
        if base is None:
            base = fr if fr.mode == "RGBA" else fr.convert("RGBA")
        else:
            paste(base, fr, 0, 0, a_in)
    base.alpha_composite(VIG)
    for e in spec["texts"]:
        draw_text_event(base, e, t)
    draw_captions(base, t)
    return post(base, t, fi, part)

def render_range(f0, f1, out):
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                            "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                            "-g", "60", "-bf", "2", out], stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        t = fi / FPS
        enc.stdin.write(render_frame(t, fi, None).tobytes())
        if (fi - f0) % 150 == 0:
            print(f"[{os.getpid()}] {fi}/{f1}", flush=True)
    enc.stdin.close(); enc.wait()
    for r in READERS.values():
        r.close()

def main():
    ensure_assets()
    a = sys.argv[1:]
    if "--still" in a:
        ts = [float(x) for x in a[a.index("--still") + 1].split(",")]
        out = a[0]
        for t in ts:
            fi = int(round(t * FPS)); READERS.clear()
            Image.fromarray(render_frame(fi / FPS, fi, None)).save(out % t)
        return
    out = a[0]
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 4
    t0 = float(a[a.index("--from") + 1]) if "--from" in a else 0.0
    t1 = float(a[a.index("--to") + 1]) if "--to" in a else DUR
    F0, F1 = int(round(t0 * FPS)), int(round(t1 * FPS))
    step = math.ceil((F1 - F0) / workers)
    parts, procs = [], []
    for k in range(workers):
        f0, f1 = F0 + k * step, min(F1, F0 + (k + 1) * step)
        if f0 >= f1:
            continue
        po = out + ".part%d.mp4" % k; parts.append(po)
        pid = os.fork()
        if pid == 0:
            render_range(f0, f1, po); os._exit(0)
        procs.append(pid)
    for pid in procs:
        _, st = os.waitpid(pid, 0)
        assert st == 0, "worker failed"
    lst = out + ".txt"
    open(lst, "w").write("".join("file '%s'\n" % os.path.abspath(p) for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    for p in parts + [lst]:
        os.remove(p)

if __name__ == "__main__":
    main()
