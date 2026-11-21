"""Crée les illustrations manquantes (graphismes vectoriels rendus en PNG) + overlays.

  media/graphics/PAPYRUS_BG.png        fond papyrus sombre 1080x1920
  media/graphics/VIGNETTE.png          vignettage (RGBA)
  media/graphics/EGYPT_MAP.png         carte de l'Égypte + Nil (1000x1000)
  media/graphics/EGYPT_Pxx.png         fragments de la carte (éclatement "quatre coins")
  media/graphics/ROUTE_MAP.png         carte Égypte -> Israël (1400x1400)
  media/graphics/ROUTE_LINE.png        tracé du trajet (même cadre, transparent)
  media/graphics/ICON_PAIN/BIERE/VIN   icônes or au trait (480x480)
  media/graphics/AFRICA.png            continent africain (1200x1300)
  media/graphics/MAGNIFIER.png         loupe (520x520)
Données cartographiques : Natural Earth via le paquet npm world-atlas (domaine public).
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

P2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
G = lambda n: os.path.join(P2, "media", "graphics", n)
FONT = lambda n: os.path.join(P2, "media", "fonts", n)
os.makedirs(os.path.join(P2, "media", "graphics"), exist_ok=True)
os.makedirs(os.path.join(P2, "media", "overlays"), exist_ok=True)
ATLAS = os.path.join(P2, "src", "data", "countries-50m.json")
GOLD = (226, 184, 98)
GOLD_L = (250, 222, 150)
rng = np.random.default_rng(7)

# ------------------------------------------------------------------ topojson
def load_countries():
    tj = json.load(open(ATLAS))
    sx, sy = tj["transform"]["scale"]; tx, ty = tj["transform"]["translate"]
    arcs = []
    for a in tj["arcs"]:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    def ring(idx):
        out = []
        for i in idx:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        return out
    res = {}
    for g in tj["objects"]["countries"]["geometries"]:
        polys = []
        if g["type"] == "Polygon":
            polys = [[ring(r) for r in g["arcs"]]]
        elif g["type"] == "MultiPolygon":
            polys = [[ring(r) for r in p] for p in g["arcs"]]
        res[str(g.get("id", ""))] = polys
    return res

def proj(lon0, lat0, lon1, lat1, w, h, pad=0):
    k = math.cos(math.radians((lat0 + lat1) / 2))
    sx = (w - 2 * pad) / ((lon1 - lon0) * k); sy = (h - 2 * pad) / (lat1 - lat0); s = min(sx, sy)
    ox = (w - (lon1 - lon0) * k * s) / 2; oy = (h - (lat1 - lat0) * s) / 2
    return lambda lon, lat: (ox + (lon - lon0) * k * s, oy + (lat1 - lat) * s)

def draw_polys(d, polys, P, fill):
    for poly in polys:
        pts = [P(*p) for p in poly[0]]   # contour extérieur seulement (silhouettes)
        if len(pts) > 2:
            d.polygon(pts, fill=fill)

def mask_of(countries, ids, P, size, ss=3):
    m = Image.new("L", (size[0] * ss, size[1] * ss), 0); d = ImageDraw.Draw(m)
    Ps = lambda lon, lat: tuple(v * ss for v in P(lon, lat))
    for i in ids:
        draw_polys(d, countries.get(i, []), Ps, 255)
    return m.resize(size, Image.LANCZOS)

def gold_fill(mask, c0=(120, 86, 40), c1=GOLD, noise=18):
    w, h = mask.size
    y = np.linspace(0, 1, h)[:, None, None]
    col = np.array(c1) * (1 - y) + np.array(c0) * y
    col = col + rng.normal(0, noise, (h, w, 1))
    col = np.clip(np.broadcast_to(col, (h, w, 3)), 0, 255).astype(np.uint8)
    im = Image.fromarray(col, "RGB").convert("RGBA"); im.putalpha(mask); return im

def outline(mask, width=3, color=GOLD_L, glow=10):
    e = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(width * 2 + 1)), mask.filter(ImageFilter.MinFilter(3)))
    line = Image.new("RGBA", mask.size, color + (0,)); line.putalpha(e)
    g = Image.new("RGBA", mask.size, color + (0,)); g.putalpha(e.filter(ImageFilter.GaussianBlur(glow)).point(lambda v: min(255, v * 2)))
    return Image.alpha_composite(g, line)

def text(d, xy, s, font, fill, anchor="mm", spacing=0):
    if not spacing:
        d.text(xy, s, font=font, fill=fill, anchor=anchor); return
    widths = [font.getlength(c) for c in s]; total = sum(widths) + spacing * (len(s) - 1)
    x = xy[0] - total / 2
    for c, cw in zip(s, widths):
        d.text((x + cw / 2, xy[1]), c, font=font, fill=fill, anchor="mm"); x += cw + spacing

# ------------------------------------------------------------------ fonds
def papyrus():
    w, h = 1080, 1920
    base = np.zeros((h, w, 3), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h * 0.45) / h) ** 2)
    glow = np.clip(1 - r * 1.6, 0, 1)[..., None]
    base += np.array([22, 15, 9]) + glow * np.array([58, 40, 20])
    fib = rng.normal(0, 1, (h // 4, w // 64)).astype(np.float32)
    fib = np.array(Image.fromarray(fib).resize((w, h), Image.BICUBIC))
    fib2 = rng.normal(0, 1, (h // 64, w // 4)).astype(np.float32)
    fib2 = np.array(Image.fromarray(fib2).resize((w, h), Image.BICUBIC))
    base += (fib * 5 + fib2 * 4)[..., None] * np.array([1.0, 0.8, 0.5])
    base += rng.normal(0, 3, (h, w, 1))
    Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).save(G("PAPYRUS_BG.png"))

def vignette():
    w, h = 1080, 1920
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w * 0.62)) ** 2 + ((yy - h / 2) / (h * 0.6)) ** 2)
    a = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 200
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); im.putalpha(Image.fromarray(a.astype(np.uint8)))
    im.save(G("VIGNETTE.png"))

# ------------------------------------------------------------------ carte Égypte + éclats
NILE = [(31.0, 31.55), (31.25, 30.05), (31.1, 29.07), (30.75, 28.1), (31.18, 27.18), (31.7, 26.56),
        (32.72, 26.16), (32.64, 25.69), (32.87, 24.98), (32.9, 24.09), (32.6, 23.3), (32.0, 22.6), (31.35, 21.9)]

def egypt(C):
    S = 1000
    P = proj(24.3, 21.6, 37.2, 31.9, S, S, pad=60)
    m = mask_of(C, ["818"], P, (S, S))
    body = gold_fill(m, (95, 66, 30), (214, 168, 84))
    # Nil
    nl = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(nl)
    d.line([P(*p) for p in NILE], fill=(40, 120, 140, 255), width=7, joint="curve")
    d.line([P(*p) for p in NILE], fill=(120, 210, 220, 255), width=3, joint="curve")
    nl.putalpha(ImageChops.multiply(nl.getchannel("A"), m))
    full = Image.alpha_composite(Image.alpha_composite(body, nl), outline(m, 2))
    full.save(G("EGYPT_MAP.png"))
    # fragments (Voronoi)
    a = np.array(m) > 127
    ys, xs = np.nonzero(a)
    seeds = []
    while len(seeds) < 14:
        i = rng.integers(len(xs)); p = (xs[i], ys[i])
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 150 ** 2 for q in seeds):
            seeds.append(p)
    seeds = np.array(seeds, float)
    yy, xx = np.mgrid[0:S, 0:S]
    lab = np.argmin((xx[..., None] - seeds[:, 0]) ** 2 + (yy[..., None] - seeds[:, 1]) ** 2, axis=-1)
    full_np = np.array(full)
    cx, cy = xs.mean(), ys.mean()
    pieces = []
    for k in range(len(seeds)):
        pm = (lab == k) & a
        if pm.sum() < 50:
            continue
        py, px = np.nonzero(pm)
        x0, x1, y0, y1 = px.min(), px.max() + 1, py.min(), py.max() + 1
        crop = full_np[y0:y1, x0:x1].copy()
        alpha = (pm[y0:y1, x0:x1] * 255).astype(np.uint8)
        crop[..., 3] = np.minimum(crop[..., 3], alpha)
        im = Image.fromarray(crop, "RGBA")
        edge = outline(Image.fromarray(alpha), 1, GOLD_L, 4)
        im = Image.alpha_composite(im, edge)
        name = "EGYPT_P%02d.png" % len(pieces)
        im.save(G(name))
        ccx, ccy = (x0 + x1) / 2, (y0 + y1) / 2
        dx, dy = ccx - cx, ccy - cy
        corner = (1 if dx >= 0 else -1, 1 if dy >= 0 else -1)
        pieces.append(dict(file=name, x=ccx - S / 2, y=ccy - S / 2, corner=corner,
                           rot=float(rng.uniform(-35, 35)), delay=float(rng.uniform(0, 0.25))))
    json.dump(dict(size=S, pieces=pieces), open(os.path.join(P2, "src", "data", "egypt_pieces.json"), "w"), indent=1)

# ------------------------------------------------------------------ carte trajet Égypte -> Israël
CAIRO = (31.24, 30.04); JERU = (35.21, 31.77)
ROUTE = [(31.24, 30.04), (32.3, 30.55), (33.3, 30.85), (34.25, 31.2), (34.75, 31.5), (35.21, 31.77)]

def route_map(C):
    S = 1400
    P = proj(27.0, 25.5, 39.5, 35.5, S, S, pad=0)
    img = Image.new("RGBA", (S, S), (14, 10, 7, 255)); d = ImageDraw.Draw(img)
    for lon in range(27, 40):  # graticule
        d.line([P(lon, 25.5), P(lon, 35.5)], fill=(70, 52, 28, 255), width=1)
    for lat in range(26, 36):
        d.line([P(27, lat), P(39.5, lat)], fill=(70, 52, 28, 255), width=1)
    land_ids = ["818", "434", "729", "376", "275", "400", "682", "422", "760", "196", "792", "368", "300", "232"]
    land = mask_of(C, land_ids, P, (S, S))
    img = Image.alpha_composite(img, gold_fill(land, (48, 34, 18), (74, 54, 30), 6))
    img = Image.alpha_composite(img, outline(land, 1, (150, 115, 60), 3))
    for ids, c0, c1 in ((["818"], (110, 76, 34), (205, 160, 80)), (["376", "275"], (130, 90, 40), (240, 200, 120))):
        m = mask_of(C, ids, P, (S, S))
        img = Image.alpha_composite(img, gold_fill(m, c0, c1, 10))
        img = Image.alpha_composite(img, outline(m, 2))
    d = ImageDraw.Draw(img)
    d.line([P(*p) for p in NILE], fill=(110, 200, 215, 255), width=4, joint="curve")
    f = ImageFont.truetype(FONT("Cinzel-Bold.ttf"), 30)
    for s, ll in (("MER MÉDITERRANÉE", (31.0, 33.6)), ("MER ROUGE", (35.6, 26.6)), ("SINAÏ", (33.8, 29.4))):
        text(d, P(*ll), s, f, (150, 120, 70, 255), spacing=6)
    img.save(G("ROUTE_MAP.png"))
    # tracé (pointillés + halo)
    ln = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(ln)
    pts = [P(*p) for p in ROUTE]
    # interpolation
    dense = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = int(math.hypot(x1 - x0, y1 - y0) / 4)
        dense += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    halo = Image.new("L", (S, S), 0); dh = ImageDraw.Draw(halo)
    dh.line(dense, fill=255, width=16, joint="curve")
    gl = Image.new("RGBA", (S, S), (255, 200, 110, 0)); gl.putalpha(halo.filter(ImageFilter.GaussianBlur(9)).point(lambda v: v * 0.7))
    ln = Image.alpha_composite(ln, gl); d = ImageDraw.Draw(ln)
    for i in range(0, len(dense) - 6, 12):
        d.line(dense[i:i + 7], fill=(255, 236, 180, 255), width=7, joint="curve")
    ln.save(G("ROUTE_LINE.png"))
    json.dump(dict(size=S, cairo=P(*CAIRO), jeru=P(*JERU)), open(os.path.join(P2, "src", "data", "route.json"), "w"))

# ------------------------------------------------------------------ icônes or au trait
def icons():
    S, ss = 480, 4
    def canvas():
        im = Image.new("L", (S * ss, S * ss), 0); return im, ImageDraw.Draw(im)
    def finish(m, name):
        m = m.resize((S, S), Image.LANCZOS)
        im = Image.new("RGBA", (S, S), GOLD_L + (0,)); im.putalpha(m)
        glow = Image.new("RGBA", (S, S), GOLD + (0,)); glow.putalpha(m.filter(ImageFilter.GaussianBlur(12)))
        Image.alpha_composite(glow, im).save(G(name))
    k = ss; lw = 9 * k
    # pain (forme d'Osiris momifié stylisé = pain allongé + motifs)
    m, d = canvas()
    d.rounded_rectangle([110 * k, 170 * k, 370 * k, 330 * k], radius=80 * k, outline=255, width=lw)
    for x in (170, 215, 260, 305):
        d.line([(x * k, 205 * k), ((x + 25) * k, 295 * k)], fill=255, width=lw // 2)
    d.arc([60 * k, 300 * k, 420 * k, 420 * k], 200, 340, fill=255, width=lw // 2)
    finish(m, "ICON_PAIN.png")
    # bière (jarre égyptienne)
    m, d = canvas()
    d.ellipse([150 * k, 150 * k, 330 * k, 380 * k], outline=255, width=lw)
    d.rectangle([195 * k, 95 * k, 285 * k, 160 * k], outline=255, width=lw)
    d.line([(180 * k, 95 * k), (300 * k, 95 * k)], fill=255, width=lw)
    d.line([(225 * k, 380 * k), (255 * k, 380 * k)], fill=255, width=lw)
    d.polygon([(200 * k, 375 * k), (280 * k, 375 * k), (240 * k, 420 * k)], outline=255, width=lw)
    for y in (220, 260, 300):
        d.arc([165 * k, (y - 30) * k, 315 * k, (y + 30) * k], 20, 160, fill=255, width=lw // 2)
    finish(m, "ICON_BIERE.png")
    # vin (calice + goutte)
    m, d = canvas()
    d.chord([130 * k, 40 * k, 350 * k, 280 * k], 0, 180, outline=255, width=lw)
    d.line([(130 * k, 160 * k), (350 * k, 160 * k)], fill=255, width=lw)
    d.line([(240 * k, 280 * k), (240 * k, 380 * k)], fill=255, width=lw)
    d.ellipse([160 * k, 370 * k, 320 * k, 420 * k], outline=255, width=lw)
    d.chord([150 * k, 170 * k, 330 * k, 260 * k], 0, 180, fill=160)
    finish(m, "ICON_VIN.png")

# ------------------------------------------------------------------ Afrique + loupe
AFRICA_IDS = "12 24 72 108 120 132 140 148 174 178 180 204 226 231 232 262 266 270 288 324 384 404 426 430 434 450 454 466 478 480 504 508 516 562 566 624 646 678 686 690 694 706 710 716 728 729 732 748 768 788 800 818 834 854 894".split()

def africa(C):
    w, h = 1200, 1300
    P = proj(-19, -36, 53, 38.5, w, h, pad=20)
    m = mask_of(C, AFRICA_IDS, P, (w, h))
    im = gold_fill(m, (88, 60, 28), (196, 150, 74), 14)
    eg = mask_of(C, ["818"], P, (w, h))
    im = Image.alpha_composite(im, gold_fill(eg, (200, 150, 70), (255, 220, 140), 6))
    im = Image.alpha_composite(im, outline(m, 3))
    im.save(G("AFRICA.png"))
    json.dump(dict(size=[w, h], egypt=P(30.5, 26.8)), open(os.path.join(P2, "src", "data", "africa.json"), "w"))

def magnifier():
    S, ss = 520, 4; k = ss
    im = Image.new("RGBA", (S * k, S * k), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([40 * k, 40 * k, 360 * k, 360 * k], fill=(255, 240, 210, 40))
    d.ellipse([40 * k, 40 * k, 360 * k, 360 * k], outline=GOLD + (255,), width=22 * k)
    d.ellipse([52 * k, 52 * k, 348 * k, 348 * k], outline=GOLD_L + (255,), width=4 * k)
    d.arc([80 * k, 80 * k, 320 * k, 320 * k], 200, 250, fill=(255, 255, 255, 170), width=10 * k)
    d.line([(318 * k, 318 * k), (470 * k, 470 * k)], fill=(90, 58, 26, 255), width=46 * k)
    d.line([(318 * k, 318 * k), (470 * k, 470 * k)], fill=GOLD + (255,), width=12 * k)
    im = im.resize((S, S), Image.LANCZOS)
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0)); sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: v * 0.6))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0)); out.alpha_composite(sh, (12, 18)); out.alpha_composite(im)
    out.save(G("MAGNIFIER.png"))
    json.dump(dict(size=S, lens=[200, 200], r=160), open(os.path.join(P2, "src", "data", "magnifier.json"), "w"))

if __name__ == "__main__":
    C = load_countries()
    papyrus(); vignette(); egypt(C); route_map(C); icons(); africa(C); magnifier()
    print("graphismes prêts")
