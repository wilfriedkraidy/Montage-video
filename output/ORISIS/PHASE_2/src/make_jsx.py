"""Génère OSIRIS_AFTER_EFFECTS_2022.jsx à partir de la même spec que le rendu (timeline.json).

Le JSX = un moteur ExtendScript (ES3) générique + un bloc de données (compositions, calques, images clés).
Les animations complexes (éclats, loupe, carte 3D) sont "bakées" à partir des fonctions du moteur Python
pour garantir la fidélité entre OSIRIS_FINAL.mp4 et le projet After Effects.
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import render as R
from PIL import Image

spec, W, H, FPS, DUR, TR, HANDLE, ZOOM = R.spec, R.W, R.H, R.FPS, R.DUR, R.TR, R.HANDLE, R.ZOOM
P2 = R.P2
rgb = lambda c, a=255: [round(c[0] / 255, 4), round(c[1] / 255, 4), round(c[2] / 255, 4)]
r3 = lambda x: round(float(x), 3)
FOOT = {}
def foot(rel):
    FOOT[rel] = rel; return rel

def K(ts, vs, e="ease"):
    return {"t": [r3(t) for t in ts], "v": [[r3(x) for x in v] if isinstance(v, (list, tuple)) else r3(v) for v in vs], "e": e}

def lin_keys(t0, t1, v0, v1, a, b):
    """clés linéaires extrapolées : v(t0)=v0, v(t1)=v1, évaluées en a et b"""
    f = lambda t: v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return K([a, b], [f(a), f(b)], "linear")

def bake(fn, a, b, step=2 / 30):
    ts, vs, t = [], [], a
    while t < b + 1e-6:
        ts.append(t); vs.append(fn(t)); t += step
    return K(ts, vs, "linear")

def text_layer(s, font, size, fill, x, y, track_px=0, glow=False, shadow=True, stroke=None, name=None, **kw):
    d = {"type": "text", "name": name or s[:30], "text": s, "font": font, "size": size, "fill": rgb(fill),
         "track": round(track_px / size * 1000), "pos": [r3(x), r3(y + size * 0.35)], "glow": glow, "shadow": shadow}
    if stroke:
        d["stroke"] = {"c": rgb(stroke[0]), "w": stroke[1]}
    d.update(kw); return d

def solid(color, w, h, name, **kw):
    d = {"type": "solid", "color": rgb(color), "w": int(w), "h": int(h), "name": name}; d.update(kw); return d

COMPS = []
def comp(cid, w, h, dur, layers):
    assert cid not in {c["id"] for c in COMPS}, "identifiant de composition en double : " + cid
    COMPS.append({"id": cid, "w": int(w), "h": int(h), "dur": r3(dur), "layers": layers}); return cid

CAMERA = {"type": "camera", "zoom": ZOOM}

def fp(cid):
    return "broll/" + cid + ".mp4"

# ------------------------------------------------------------------ scènes
def scene(i, s):
    t0, t1 = s["t0"], s["t1"]; d = t1 - t0; L = lambda t: t - t0 + TR / 2
    a, b = 0.0, d + TR                         # durée du précomp
    kind = s["kind"]; Ls = []
    bgpap = lambda: {"type": "footage", "src": foot("graphics/PAPYRUS_BG.png"), "name": "papyrus", "scale": lin_keys(TR / 2, d + TR / 2, 100, 106, a, b)}
    if kind == "A":
        Ls.append({"type": "footage", "src": foot("aroll/AROLL_GRADED.mp4"), "name": "A-ROLL", "start": r3(-(t0 - TR / 2)),
                   "anchor": [540, 760], "pos": [540, 760], "scale": lin_keys(TR / 2, d + TR / 2, s["s"][0] * 100, s["s"][1] * 100, a, b)})
    elif kind == "FULL":
        Ls.append({"type": "footage", "src": foot(fp(s["clip"])), "name": s["clip"], "start": r3(TR / 2 - HANDLE),
                   "scale": lin_keys(TR / 2, d + TR / 2, s["s"][0] * 100, s["s"][1] * 100, a, b)})
        if s.get("end"):
            Ls.append(solid((0, 0, 0), W, H, "assombrir fin", opacity=K([L(144.4), L(145.6)], [0, 62])))
    elif kind == "PLATE":
        k = max(W / 1280, H / 548) * 100
        Ls.append({"type": "footage", "src": foot(fp(s["clip"])), "name": "fond flou", "start": r3(TR / 2 - HANDLE),
                   "scale": lin_keys(TR / 2, d + TR / 2, k * 1.12, k * 1.2, a, b),
                   "fx": [{"m": "ADBE Gaussian Blur 2", "p": {"ADBE Gaussian Blur 2-0001": 60, "ADBE Gaussian Blur 2-0003": 1}}]})
        Ls.append(solid((0, 0, 0), W, H, "assombrir", opacity=60))
        sub = comp(s["id"] + "_VIDEO", 1060, 454, b, [
            {"type": "footage", "src": foot(fp(s["clip"])), "name": s["clip"], "start": r3(TR / 2 - HANDLE), "scale": 1060 / 1280 * 100},
            {"type": "rect", "name": "filet or", "w": 1060, "h": 454, "stroke": rgb(R.GOLD), "sw": 3},
            {"type": "rect", "name": "filet fin", "w": 1046, "h": 440, "stroke": rgb(R.GOLD_L), "sw": 1, "opacity": 45}])
        Ls.append({"type": "comp", "src": sub, "name": "plan 3D", "threeD": True, "pos3": [540, 960, None],
                   "posZ": K([L(t0), L(t1)], [s["z"][0], s["z"][1]]), "rotY": K([L(t0), L(t1)], [s["ry"][0], s["ry"][1]]),
                   "fx": [{"m": "ADBE Drop Shadow", "p": {"ADBE Drop Shadow-0004": 14, "ADBE Drop Shadow-0005": 44}}]})
        Ls.append({"type": "footage", "src": foot("graphics/PLATE_ORNAMENT.png"), "name": "ornement", "opacity": K([L(t0), L(t0) + 0.6], [0, 100])})
        Ls.append(CAMERA)
    elif kind == "CARD":
        im = Image.open(R.MED("stills", s["img"] + ".png")); k = max(W / im.width, H / im.height) * 100
        Ls.append({"type": "footage", "src": foot("stills/" + s["img"] + ".png"), "name": "fond flou",
                   "scale": lin_keys(TR / 2, d + TR / 2, k * 1.1, k * 1.22, a, b),
                   "fx": [{"m": "ADBE Gaussian Blur 2", "p": {"ADBE Gaussian Blur 2-0001": 70, "ADBE Gaussian Blur 2-0003": 1}}]})
        Ls.append(solid((0, 0, 0), W, H, "assombrir", opacity=58))
        Ls.append({"type": "footage", "src": foot("graphics/CARD_" + s["img"] + ".png"), "name": "carte 3D", "threeD": True,
                   "pos3": [540, 960, None], "posZ": K([L(t0), L(t1)], s["z"]), "rotX": K([L(t0), L(t1)], s["rx"]),
                   "rotY": K([L(t0), L(t1)], s["ry"])})
        Ls.append(CAMERA)
    elif kind == "SPLIT":
        Ls.append(bgpap())
        sep = 50 if s.get("split") else 0
        kin = [L(t0), L(t0) + 0.6]
        sepk = [L(t0), L(t0) + 0.7]
        Ls.append({"type": "footage", "src": foot("graphics/SPLIT_" + s["top"] + ".png"), "name": "carte haut", "threeD": True,
                   "posX": K(kin, [480, 540]), "posY": K(sepk, [470, 470 - sep]), "posZ": lin_keys(TR / 2, d + TR / 2, 80, -30, a, b),
                   "rotY": lin_keys(TR / 2, d + TR / 2, -9, -3, a, b), "opacity": K(kin, [0, 100])})
        sub = comp(s["id"] + "_BAS", 860, 560, b, [
            {"type": "footage", "src": foot(fp(s["bottom"])), "name": s["bottom"], "start": r3(TR / 2 - HANDLE), "scale": 560 / 548 * 100},
            {"type": "rect", "name": "filet or", "w": 860, "h": 560, "stroke": rgb(R.GOLD), "sw": 6},
            {"type": "rect", "name": "filet fin", "w": 838, "h": 538, "stroke": rgb(R.GOLD_L), "sw": 1, "opacity": 45}])
        Ls.append({"type": "comp", "src": sub, "name": "carte bas", "threeD": True,
                   "posX": K(kin, [600, 540]), "posY": K(sepk, [1200, 1200 + sep]), "posZ": lin_keys(TR / 2, d + TR / 2, 80, -30, a, b),
                   "rotY": lin_keys(TR / 2, d + TR / 2, 9, 3, a, b), "opacity": K(kin, [0, 100]),
                   "fx": [{"m": "ADBE Drop Shadow", "p": {"ADBE Drop Shadow-0004": 14, "ADBE Drop Shadow-0005": 44}}]})
        for lab, y, dy in zip(s["labels"], (705, 1432), (-sep, sep)):
            Ls.append(text_layer(lab, "Cinzel-Black", 58, R.GOLD_L, 540, y, 8, glow=True, opacity=K(kin, [0, 100]),
                                 posKeys=K([L(t0), L(t0) + 0.7], [[540, y + 20], [540, y + dy + 20]])))
        sym = "SYMBOL_NEQ.png" if s.get("split") else "SYMBOL_EQ.png"
        Ls.append({"type": "footage", "src": foot("graphics/" + sym), "name": "symbole", "pos": [540, 836],
                   "scale": K([L(t0) + 0.35 + i * 0.4 / 8 for i in range(9)], [[R.back_out(i / 8) * 80] * 2 for i in range(9)], "linear")})
        if not s.get("split"):
            Ls.append(text_layer("?", "Cinzel-Black", 90, R.GOLD_L, 610, 836, 0, glow=True, opacity=K([L(t0) + 0.6, L(t0) + 0.9], [0, 100])))
    elif kind == "MAP_EGYPT":
        Ls.append(bgpap())
        sh = s["shatter"]
        zc = lambda t: R.lerp(220, -60, R.ease((t - t0) / d)); rx = lambda t: R.lerp(18, 8, R.ease((t - t0) / d))
        Ls.append({"type": "footage", "src": foot("graphics/EGYPT_MAP.png"), "name": "carte Egypte", "threeD": True,
                   "pos3": [540, 900, None], "posZ": K([L(t0), L(t1)], [220, -60]), "rotX": K([L(t0), L(t1)], [18, 8]),
                   "out": r3(L(sh))})
        Ls.append(text_layer("ÉGYPTE", "Cinzel-Black", 84, R.CREAM, 540, 300, 18, glow=True,
                             opacity=K([L(t0), L(t0) + 0.5, L(sh) - 0.25, L(sh)], [0, 100, 100, 0]), out=r3(L(sh))))
        size = R.EG["size"]
        for p in R.EG["pieces"]:
            def st(t, p=p):
                q = R.ease_out((t - sh - p["delay"]) / 1.1)
                tx, ty = p["x"] * 0.55 + p["corner"][0] * 270, p["y"] * 0.55 + p["corner"][1] * 520
                x, y = R.lerp(p["x"], tx, q), R.lerp(p["y"], ty, q)
                cx, cy = R.project([(size / 2 + x, size / 2 + y)], (W / 2, 900, zc(t)), rx(t), 0, 1.0, (size / 2, size / 2))[0]
                kz = ZOOM / (ZOOM + zc(t))
                return [cx, cy], p["rot"] * q, R.lerp(1.0, 0.62, q) * kz * 100, R.lerp(100, 90, q)
            ts = [sh + i / 15 for i in range(int((t1 + TR / 2 - sh) * 15) + 1)]
            vals = [st(t) for t in ts]
            Ls.append({"type": "footage", "src": foot("graphics/" + p["file"]), "name": p["file"][:-4], "in": r3(L(sh)),
                       "posKeys": K([L(t) for t in ts], [v[0] for v in vals], "linear"),
                       "rot": K([L(t) for t in ts], [v[1] for v in vals], "linear"),
                       "scale": K([L(t) for t in ts], [[v[2], v[2]] for v in vals], "linear"),
                       "opacity": K([L(t) for t in ts], [v[3] for v in vals], "linear")})
        Ls.append(CAMERA)
    elif kind == "ICONS":
        Ls.append(bgpap())
        Ls.append(solid(R.GOLD, 840, 2, "ligne", pos=[540, 1060], opacity=67, scale=K([L(t0), L(t0) + 0.8], [[0, 100], [100, 100]])))
        for i, ((icn, lab), at) in enumerate(zip((("ICON_PAIN", "PAIN"), ("ICON_BIERE", "BIÈRE"), ("ICON_VIN", "VIN")), s["at"])):
            x = 200 + 340 * i
            ks = [L(at) + 0.45 * j / 8 for j in range(9)]
            Ls.append({"type": "footage", "src": foot("graphics/" + icn + ".png"), "name": icn, "pos": [x, 880], "in": r3(L(at)),
                       "scale": K(ks, [[R.back_out(j / 8) * 72] * 2 for j in range(9)], "linear"), "opacity": K([L(at), L(at) + 0.3], [0, 100])})
            Ls.append(text_layer(lab, "Cinzel-Black", 54, R.GOLD_L, x, 1130, 10, glow=True, inP=r3(L(at)),
                                 opacity=K([L(at), L(at) + 0.3], [0, 100]), posKeys=K([L(at), L(at) + 0.45], [[x, 1150 + 54 * 0.35], [x, 1130 + 54 * 0.35]])))
    elif kind == "MAP_ROUTE":
        Ls.append(bgpap())
        S = R.RT["size"]; cai, jer = R.RT["cairo"], R.RT["jeru"]
        x0, x1 = cai[0] - 12, jer[0] + 12
        dr0, dr1 = s["draw"]
        pl = [{"type": "footage", "src": foot("graphics/ROUTE_MAP.png"), "name": "carte"},
              {"type": "footage", "src": foot("graphics/ROUTE_LINE.png"), "name": "trajet",
               "fx": [{"m": "ADBE Linear Wipe", "p": {"ADBE Linear Wipe-0002": 270, "ADBE Linear Wipe-0003": 0},
                       "k": {"ADBE Linear Wipe-0001": K([L(dr0), L(dr1)], [100 * (1 - x0 / S), 100 * (1 - x1 / S)])}}]}]
        for pt, lab, at in ((cai, "ÉGYPTE", dr0 - 0.3), (jer, "ISRAËL", dr1 - 0.1)):
            ks = [L(at) + 0.4 * j / 6 for j in range(7)]
            pl.append({"type": "ellipse", "name": "repère " + lab, "pos": [r3(pt[0]), r3(pt[1])], "r": 14, "fill": [1, 0.925, 0.706],
                       "ring": rgb(R.GOLD_L), "in": r3(L(at)), "scale": K(ks, [[R.back_out(j / 6) * 100] * 2 for j in range(7)], "linear"),
                       "expr": "var k = 1; if (time > %.3f) { k = 1 + 0.25 * Math.sin((time - %.3f) * 6); } mul(value, k);" % (L(at) + 0.4, L(at))})
            ox, oy = (0, 60) if lab == "ÉGYPTE" else (40, -110)
            pl.append(text_layer(lab, "Cinzel-Black", 64, R.GOLD_L, pt[0] + ox, pt[1] + oy, 8, glow=True, inP=r3(L(at)),
                                 opacity=K([L(at), L(at) + 0.4], [0, 100])))
        sub = comp(s["id"] + "_PLAN", S, S, b, pl)
        mid = ((cai[0] + jer[0]) / 2, (cai[1] + jer[1]) / 2)
        u = lambda t: (t - t0) / d
        ts = [t0 - TR / 2 + j * (d + TR) / 16 for j in range(17)]
        Ls.append({"type": "comp", "src": sub, "name": "carte 3D", "threeD": True, "anchor": [r3(mid[0]), r3(mid[1]), 0],
                   "pos3": [540, 880, None], "posZ": K([L(t) for t in ts], [R.lerp(500, 60, R.ease_out(u(t) * 1.2)) for t in ts], "linear"),
                   "rotX": K([L(t) for t in ts], [R.lerp(32, 22, u(t)) for t in ts], "linear"),
                   "rotY": K([L(t) for t in ts], [R.lerp(-6, 4, u(t)) for t in ts], "linear")})
        Ls.append(text_layer("LE CULTE D'OSIRIS VOYAGE", "Cinzel-Bold", 44, R.CREAM, 540, 330, 8,
                             opacity=K([L(t0) + 0.5, L(t0) + 1.0, L(t1) - 0.4, L(t1)], [0, 100, 100, 0])))
        Ls.append(CAMERA)
    elif kind == "AFRICA":
        Ls.append(bgpap())
        aw, ah = R.AF["size"]
        u = lambda t: (t - t0) / d
        pos = lambda t: (W / 2, 1000, R.lerp(260, 0, R.ease(u(t))))
        rxf = lambda t: R.lerp(14, 6, u(t)); ryf = lambda t: R.lerp(-12, 8, R.ease(u(t)))
        ts = [t0 - TR / 2 + j * (d + TR) / 16 for j in range(17)]
        Ls.append({"type": "footage", "src": foot("graphics/AFRICA.png"), "name": "Afrique 3D", "threeD": True, "scale3": 82,
                   "pos3": [540, 1000, None], "posZ": K([L(t) for t in ts], [pos(t)[2] for t in ts], "linear"),
                   "rotX": K([L(t) for t in ts], [rxf(t) for t in ts], "linear"), "rotY": K([L(t) for t in ts], [ryf(t) for t in ts], "linear")})
        def mg(t):
            ex, ey = R.project([tuple(R.AF["egypt"])], pos(t), rxf(t), ryf(t), 0.82, (aw / 2, ah / 2))[0]
            q = R.ease((t - t0 - 0.3) / 2.6)
            return [R.lerp(180, ex, q), R.lerp(1500, ey, q)]
        ts = [t0 - TR / 2 + j / 10 for j in range(int((d + TR) * 10) + 1)]
        Ls.append({"type": "footage", "src": foot("graphics/MAGNIFIER.png"), "name": "loupe", "anchor": R.MG["lens"],
                   "posKeys": K([L(t) for t in ts], [mg(t) for t in ts], "linear"), "opacity": K([L(t0), L(t0) + 0.5], [0, 100])})
        Ls.append(CAMERA)
    cid = comp(s["id"] + "_" + kind, W, H, b, Ls)
    # calque dans la comp principale : fondu enchaîné + sur-zoom de transition
    main = {"type": "comp", "src": cid, "name": cid, "start": r3(t0 - TR / 2)}
    ts, op, sc = [], [], []
    if i > 0:
        ts += [t0 - TR / 2, t0 + TR / 2]; op += [0, 100]; sc += [105, 100]
    if i < len(spec["scenes"]) - 1:
        ts += [t1 - TR / 2, t1 + TR / 2]; op += [100, 100]; sc += [100, 105]
    if ts:
        main["opacity"] = K(ts, op); main["scale"] = K(ts, [[v, v] for v in sc])
    return main

# ------------------------------------------------------------------ textes animés (précomps plein cadre)
def text_event(n, e):
    st, t0, t1 = e["style"], e["t0"], e["t1"]
    d = t1 - t0; Ls = []
    KT = lambda ts, vs, e="ease": K([t0 + x for x in ts], vs, e)   # clés du calque dans la comp principale
    def io(ti, to):  # durées d'entrée / sortie compressées si l'événement est court
        k = min(1.0, (d - 0.05) / (ti + to)); return ti * k, to * k
    name = "TXT_%02d_%s" % (n, st)
    lay = {"type": "comp", "name": name, "start": r3(t0)}
    if st == "hero":
        y = e["y"] or 300
        size = R.fit(e["text"], "Cinzel-Black", 150, 960, 34)
        Ls.append(text_layer(e["text"], "Cinzel-Black", size, R.GOLD_L, 540, y, 6, glow=True, trackKeys=K([0, 0.55], [34, 6]), name="titre"))
        if e["sub"]:
            Ls.append(text_layer(e["sub"], "Cinzel-Bold", 62, R.CREAM, 540, y + 122, 14, trackKeys=K([0.18, 0.73], [36, 14]),
                                 opacity=K([0.18, 0.73], [0, 100]), posKeys=K([0.18, 0.73], [[540, y + 142 + 22], [540, y + 122 + 22]]), name="sous-titre"))
        ti, to = io(0.55, 0.35)
        lay.update(anchor=[540, y], pos=[540, y], opacity=KT([0, ti, d - to, d], [0, 100, 100, 0]),
                   scale=KT([0, ti, d - to, d], [[116, 116], [100, 100], [100, 100], [97, 97]]))
    elif st == "chapter":
        y = e["y"] or 900
        if not e["y"]:
            Ls.append(solid((0, 0, 0), W, H, "voile", opacity=41))
        sub_w = R.FONT("Cinzel-Bold", 44).getlength(e["sub"]) + 18 * (len(e["sub"]) - 1)
        hw = (sub_w + 80) / 2 - 30
        Ls.append(text_layer(e["sub"], "Cinzel-Bold", 44, R.GOLD, 540, y - 95, 18, name="chapitre"))
        for side in (-1, 1):
            Ls.append(solid(R.GOLD, 150, 2, "filet", opacity=86, anchor=[150 if side < 0 else 0, 1],
                            pos=[r3(540 + side * (hw + 20)), y - 91], scale=K([0, 0.6], [[0, 100], [100, 100]])))
        size = R.fit(e["text"], "Cinzel-Black", 96, 980, 4)
        Ls.append(text_layer(e["text"], "Cinzel-Black", size, R.CREAM, 540, y + 10, 4, glow=True, trackKeys=K([0, 0.6], [26, 4]), name="titre"))
        ti, to = io(0.35, 0.4)
        lay.update(opacity=KT([0, ti, d - to, d], [0, 100, 100, 0]))
    elif st == "tag":
        y = e["y"] or 1330
        size = R.fit(e["text"], "Cinzel-Bold", 46, 900, 6)
        tw = R.FONT("Cinzel-Bold", size).getlength(e["text"]) + 6 * (len(e["text"]) - 1)
        bw = tw + 60
        Ls.append(solid((8, 5, 2), bw, 88, "bandeau", pos=[540, y], opacity=56))
        Ls.append(solid(R.GOLD, bw, 2, "filet haut", pos=[540, y - 43], opacity=90))
        Ls.append(solid(R.GOLD, bw, 2, "filet bas", pos=[540, y + 43], opacity=90))
        Ls.append(text_layer(e["text"], "Cinzel-Bold", size, R.GOLD_L, 540, y + 2, 6, name="texte"))
        ti, to = io(0.4, 0.3)
        lay.update(opacity=KT([0, ti, d - to, d], [0, 100, 100, 0]), posKeys=KT([0, ti], [[540, 960 + 26], [540, 960]]))
    elif st == "stamp":
        y = e["y"] or 1150
        size = R.fit(e["text"], "Cinzel-Black", 84, 820, 4)
        tw = R.FONT("Cinzel-Black", size).getlength(e["text"]) + 4 * (len(e["text"]) - 1)
        Ls.append({"type": "null", "name": "tampon", "pos": [540, y], "rot": -7})
        Ls.append(dict(text_layer(e["text"], "Cinzel-Black", size, R.RED, 0, 0, 4, shadow=False, name="texte"), parent=1))
        Ls.append({"type": "rect", "name": "cadre", "w": r3(tw + 60), "h": 150, "stroke": rgb(R.RED), "sw": 9, "pos": [0, 0], "parent": 1})
        ti, to = io(0.16, 0.3)
        lay.update(anchor=[540, y], pos=[540, y], opacity=KT([0, ti, d - to, d], [0, 100, 100, 0]),
                   scale=KT([0, 0.16], [[180, 180], [100, 100]], "linear"))
    elif st == "end":
        Ls.append(text_layer(e["text"], "Cinzel-Black", 200, R.GOLD_L, 540, 860, 24, glow=True, trackKeys=K([0, 1.2], [70, 24]), name="titre"))
        Ls.append(text_layer(e["sub"], "Cinzel-Bold", 44, R.CREAM, 540, 1010, 14, opacity=K([0.4, 1.4], [0, 100]), name="sous-titre"))
        lay.update(opacity=KT([0, 0.8], [0, 100]))
    lay["src"] = comp(name, W, H, d, Ls)
    return lay

# ------------------------------------------------------------------ sous-titres
def captions():
    f = R.FONT("Montserrat-ExtraBold", 60); space = f.getlength(" ")
    out = []
    for ci, c in enumerate(R.CAP):
        words = [w["w"] for w in c["words"]]
        lines, cur, cw = [], [], 0
        for w in words:
            lw = f.getlength(w)
            if cur and cw + space + lw > 940:
                lines.append(cur); cur, cw = [], 0
            cur.append(w); cw += (space if cw else 0) + lw
        lines.append(cur)
        txt = "\r".join(" ".join(l) for l in lines)
        nxt = R.CAP[ci + 1]["start"] if ci + 1 < len(R.CAP) else c["end"] + 0.6
        a, b = c["start"] - 0.04, min(c["end"] + 0.35, nxt - 0.02)
        ts, st = [a], [0]
        for i, w in enumerate(c["words"]):
            ts.append(max(a + 0.001, w["s"] - 0.02)); st.append(i)
        # dédoublonnage des temps
        T2, S2 = [], []
        for t, v in zip(ts, st):
            if T2 and t - T2[-1] < 1 / 60:
                S2[-1] = v
            else:
                T2.append(t); S2.append(v)
        hl = {"t": [r3(t) for t in T2], "start": S2, "end": [v + (1 if k else 0) for k, v in enumerate(S2)]}
        nl = len(lines)
        y0 = R.CAP_Y - (76 * nl + 60) / 2 + 30 + f.getmetrics()[0]
        out.append({"type": "text", "name": "ST %02d" % (ci + 1), "text": txt, "font": "Montserrat-ExtraBold", "size": 60, "lead": 76,
                    "fill": [1, 1, 1], "stroke": {"c": rgb((18, 12, 6)), "w": 8}, "track": 0, "pos": [540, r3(y0)], "shadow": True,
                    "in": r3(a), "out": r3(b), "hl": hl, "hlColor": rgb((245, 196, 81)),
                    "anchorScale": [540, R.CAP_Y], "scale": K([a, a + 0.1], [[93, 93], [100, 100]]), "opacity": K([a, a + 0.067], [0, 100])})
    return out

def build():
    main_layers = [scene(i, s) for i, s in enumerate(spec["scenes"])]
    main_layers.append({"type": "footage", "src": foot("graphics/VIGNETTE.png"), "name": "vignettage"})
    for n, e in enumerate(spec["texts"]):
        main_layers.append(text_event(n + 1, e))
    cap = comp("SOUS_TITRES", W, H, DUR, captions())
    main_layers.append({"type": "comp", "src": cap, "name": "SOUS_TITRES"})
    ft, fv = [0], [0]
    for tf in sorted(spec["flashes"]):
        for t, v in ((tf - 0.15, 0), (tf, 55), (tf + 0.5, 0)):
            if t > ft[-1] + 1e-3:
                ft.append(t); fv.append(v)
    main_layers.append(solid((0, 0, 0), W, H, "ECLAIRS (rampe radiale)", blend="ADD", opacity=K(ft, fv, "linear"),
                             fx=[{"m": "ADBE Ramp", "p": {"ADBE Ramp-0001": [669.6, 691.2], "ADBE Ramp-0002": [1, 0.698, 0.376],
                                                          "ADBE Ramp-0003": [1569.6, 691.2], "ADBE Ramp-0004": [0, 0, 0], "ADBE Ramp-0005": 2}}]))
    main_layers.append({"type": "adjustment", "name": "GRAIN", "fx": [{"m": "ADBE Noise", "p": {"ADBE Noise-0001": 3.2, "ADBE Noise-0002": 0}}]})
    main_layers.append(solid((0, 0, 0), W, H, "FONDU NOIR", opacity=K([0, 0.4, DUR - 0.9, DUR], [100, 0, 0, 100], "linear")))
    for st in ("VOICE_STEM", "MUSIC", "SFX"):
        main_layers.append({"type": "footage", "src": foot("audio/%s.wav" % st), "name": st})
    comp("OSIRIS_FINAL", W, H, DUR, main_layers)
    data = {"comp": {"w": W, "h": H, "fps": FPS, "dur": DUR}, "footage": sorted(FOOT), "comps": COMPS, "main": "OSIRIS_FINAL"}
    js = open(os.path.join(P2, "src", "jsx_engine.js"), encoding="utf-8").read()
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    out = js.replace("/*__DATA__*/null", payload)
    path = os.path.join(P2, "OSIRIS_AFTER_EFFECTS_2022.jsx")
    open(path, "w", encoding="utf-8").write(out)
    print(path, len(out) // 1024, "Ko,", len(COMPS), "compositions,", len(FOOT), "médias")

if __name__ == "__main__":
    build()
