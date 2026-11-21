"""OSIRIS – Phase 2 : spécification unique du montage motion design.

Cette spec alimente à la fois :
  * render.py  -> rendu final OSIRIS_FINAL.mp4
  * make_jsx.py -> script After Effects 2022 (OSIRIS_AFTER_EFFECTS_2022.jsx)
Les temps sont exprimés en secondes sur la timeline finale (voix = montage Phase 1).
"""
import json, os

FPS = 30
W, H = 1080, 1920
DUR = 147.4          # voix 144.4 s + carton de fin
VOICE_DUR = 144.4
HANDLE = 0.5         # marge avant/après chaque clip B-roll préparé
TR = 0.40            # durée des fondus entre plans
CAM_ZOOM = 1800.0    # caméra AE (px) – projection 2.5D

V5 = "media/docs/ORISIS/ILLUSTRATION/Osiris-The-Murdered-SnapYT.App.mp4"
V3 = "media/docs/ORISIS/ILLUSTRATION/Jesus-vs-Osiris-SnapYT.App.mp4"
ILL = "media/docs/ORISIS/ILLUSTRATION/"

# ---------------------------------------------------------------- B-roll sources
# clip id : (source, temps source au début du plan, recadrage)
#   crop "scope"    : 1280x548 haut de l'image (supprime les sous-titres anglais incrustés)
#   crop "vertical" : supprime le badge "subscribe" et remet en 1080x1920
CLIPS = {
    "V5_OSI_CLOSE":   (V5, 10.0,  "scope"),
    "V5_OSI_THRONE":  (V5, 1.0,   "scope"),
    "V5_FARM":        (V5, 105.5, "scope"),
    "V5_SET_CHEST":   (V5, 170.5, "scope"),
    "V5_ANUBIS":      (V5, 258.0, "scope"),
    "V5_ISIS_REVIVE": (V5, 346.0, "scope"),
    "V5_ISIS_BABY":   (V5, 363.5, "scope"),
    "V5_COURT":       (V5, 380.0, "scope"),
    "V5_WEIGHING":    (V5, 433.0, "scope"),
    "V5_WORSHIP":     (V5, 471.0, "scope"),
    "V5_GRAIN_BED":   (V5, 573.0, "scope"),
    "V5_OSI_FACE":    (V5, 555.5, "scope"),
    "V3_ISIS_NIGHT":  (V3, 32.6, "vertical"),
    "V3_WHEAT":       (V3, 113.0, "vertical"),
    "V3_JESUS_A":     (V3, 106.25, "vertical"),
    "V3_TOMB_OPEN":   (V3, 98.6,  "vertical"),
    "V3_JESUS_B":     (V3, 108.9, "vertical"),
    "V3_DOOR":        (V3, 120.4, "vertical"),
}

# images fixes nettoyées (recadrage des textes / filigranes) : id -> (fichier, box relative l,t,r,b)
STILLS = {
    "ST_BLACK_JESUS":   (ILL + "images (6).jpeg", (0, 0, 1, 0.86)),
    "ST_BLACK_CHRIST":  (ILL + "photo-jean-francois-roche-1775634261.jpg", (0, 0, 1, 1)),
    "ST_RELIEF":        (ILL + "osiris-isis-ancient-egyptian-relief-throne-hieroglyphs.jpg", (0, 0, 1, 1)),
    "ST_FAMILY":        (ILL + "osiris, sa femme et son frere.png", (0, 0, 1, 1)),
    "ST_LASTSUPPER":    (ILL + "vin-et-religion.jpg", (0, 0, 1, 1)),
    "ST_ICON_SUPPER":   (ILL + "lksuo6rrdbsa1.jpg", (0, 0, 1, 1)),
    "ST_ISIS_MARIE":    (ILL + "images (4).jpeg", (0, 0, 1, 1)),
    "ST_HORUS_JESUS":   (ILL + "images (5).jpeg", (0, 0, 1, 1)),
    "ST_CRUCIFIX":      (ILL + "images (7).jpeg", (0, 0, 1, 1)),
}

# ---------------------------------------------------------------- scènes
# A     : face caméra (AROLL_GRADED), léger travelling avant/arrière
# FULL  : B-roll vertical plein cadre
# PLATE : B-roll 16:9 "scope" en plan 3D flottant + fond flouté (2.5D)
# CARD  : image fixe en carte 3D + fond flouté (2.5D)
# SPLIT : deux cartes empilées (comparaison)
# MAP_EGYPT / ICONS / MAP_ROUTE / AFRICA : graphismes créés
S = []
def sc(t0, t1, kind, **kw):
    d = dict(id="S%02d" % (len(S) + 1), t0=t0, t1=t1, kind=kind); d.update(kw); S.append(d)

sc(0.00,   3.45,  "CARD",  img="ST_BLACK_JESUS", ry=(-7, 4), rx=(3, -2), z=(120, -60))
sc(3.45,   8.55,  "A",     s=(1.00, 1.06))
sc(8.55,   12.10, "SPLIT", top="ST_BLACK_CHRIST", bottom="V5_OSI_CLOSE", labels=("JÉSUS", "OSIRIS"))
sc(12.10,  15.45, "PLATE", clip="V5_OSI_THRONE", ry=(-9, 3), z=(150, -80))
sc(15.45,  18.20, "PLATE", clip="V5_FARM", ry=(6, -4), z=(60, -90))
sc(18.20,  19.80, "CARD",  img="ST_RELIEF", ry=(-5, 4), rx=(2, -1), z=(80, -40))
sc(19.80,  22.26, "PLATE", clip="V5_SET_CHEST", ry=(-6, 5), z=(100, -60))
sc(22.26,  26.28, "MAP_EGYPT", shatter=24.45)
sc(26.28,  30.38, "FULL",  clip="V3_ISIS_NIGHT", s=(1.00, 1.08))
sc(30.38,  34.16, "PLATE", clip="V5_ANUBIS", ry=(7, -5), z=(80, -80))
sc(34.16,  44.10, "A",     s=(1.00, 1.08))
sc(44.10,  47.44, "PLATE", clip="V5_ISIS_REVIVE", ry=(-8, 4), z=(120, -60))
sc(47.44,  49.72, "PLATE", clip="V5_ISIS_BABY", ry=(5, -3), z=(40, -80))
sc(49.72,  55.60, "CARD",  img="ST_FAMILY", ry=(-8, 6), rx=(4, -3), z=(160, -100))
sc(55.60,  58.78, "A",     s=(1.08, 1.02))
sc(58.78,  61.80, "PLATE", clip="V5_COURT", ry=(-6, 4), z=(100, -60))
sc(61.80,  66.42, "PLATE", clip="V5_WEIGHING", ry=(8, -6), z=(120, -100))
sc(66.42,  70.02, "PLATE", clip="V5_WORSHIP", ry=(-5, 5), z=(60, -120))
sc(70.02,  72.50, "FULL",  clip="V3_WHEAT", s=(1.10, 1.02))
sc(72.50,  76.44, "A",     s=(1.00, 1.06))
sc(76.44,  80.20, "PLATE", clip="V5_GRAIN_BED", ry=(-7, 5), z=(120, -80))
sc(80.20,  83.10, "ICONS", at=(80.35, 81.30, 82.22))
sc(83.10,  86.38, "A",     s=(1.06, 1.00))
sc(86.38,  89.88, "CARD",  img="ST_LASTSUPPER", ry=(6, -5), rx=(-2, 2), z=(120, -80))
sc(89.88,  92.44, "FULL",  clip="V3_JESUS_A", s=(1.12, 1.02))
sc(92.44,  95.50, "A",     s=(1.00, 1.05))
sc(95.50,  100.62, "MAP_ROUTE", draw=(96.3, 99.2))
sc(100.62, 103.90, "CARD", img="ST_ICON_SUPPER", ry=(-6, 4), rx=(3, -2), z=(140, -60))
sc(103.90, 104.82, "FULL", clip="V3_TOMB_OPEN", s=(1.00, 1.05))
sc(104.82, 106.92, "CARD", img="ST_ISIS_MARIE", ry=(5, -4), rx=(2, -2), z=(100, -40))
sc(106.92, 109.90, "CARD", img="ST_HORUS_JESUS", ry=(-5, 5), rx=(-2, 2), z=(100, -60))
sc(109.90, 111.54, "FULL", clip="V3_JESUS_B", s=(1.00, 1.06))
sc(111.54, 116.06, "CARD", img="ST_CRUCIFIX", ry=(-6, 5), rx=(4, -2), z=(160, -80))
sc(116.06, 123.90, "A",    s=(1.00, 1.08))
sc(123.90, 128.00, "SPLIT", top="ST_BLACK_CHRIST", bottom="V5_OSI_FACE", labels=("JÉSUS", "OSIRIS · HORUS"), split=True)
sc(128.00, 135.08, "A",    s=(1.07, 1.00))
sc(135.08, 139.86, "AFRICA")
sc(139.86, 142.30, "A",    s=(1.00, 1.04))
sc(142.30, DUR,    "FULL", clip="V3_DOOR", s=(1.00, 1.10), end=True)

# ---------------------------------------------------------------- textes animés
# style : chapter | hero | tag | stamp | label
T = []
def tx(t0, t1, style, text, sub=None, y=None):
    T.append(dict(t0=t0, t1=t1, style=style, text=text, sub=sub, y=y))

tx(0.30,   3.30,  "hero",    "ISSA", sub="JÉSUS ?")
tx(12.15,  15.30, "chapter", "QUI ÉTAIT OSIRIS ?", sub="CHAPITRE I")
tx(15.60,  18.10, "tag",     "DIEU DE LA FERTILITÉ")
tx(18.30,  19.70, "tag",     "ISIS · SON ÉPOUSE")
tx(19.90,  22.20, "tag",     "SETH · SON FRÈRE")
tx(24.60,  26.20, "tag",     "LES QUATRE COINS DE L'ÉGYPTE")
tx(30.50,  34.05, "tag",     "ANUBIS")
tx(36.20,  38.30, "tag",     "LE MONDE DES MORTS")
tx(47.55,  49.65, "tag",     "HORUS")
tx(50.00,  55.40, "hero",    "UNE NAISSANCE", sub="HORS DU COMMUN")
tx(56.80,  58.70, "tag",     "PHARAON VIVANT = HORUS")
tx(58.90,  61.70, "hero",    "FILS DE DIEU")
tx(61.95,  66.30, "tag",     "PHARAON MORT → OSIRIS")
tx(66.55,  69.90, "hero",    "ROI DES MORTS")
tx(70.07,  72.45, "chapter", "LE CULTE D'OSIRIS", sub="CHAPITRE II")
tx(76.55,  80.10, "tag",     "UN PAIN À L'IMAGE D'OSIRIS")
tx(84.76,  86.30, "tag",     "LE VIN = LE SANG")
tx(86.50,  89.80, "hero",    "SON CORPS", sub="SON SANG")
tx(89.93,  92.40, "chapter", "LE MYSTÈRE ISSA", sub="CHAPITRE III")
tx(92.55,  95.40, "tag",     "UN PROPHÈTE VENU D'ÉGYPTE")
tx(100.70, 103.80, "tag",    "CORPS & SANG → EUCHARISTIE")
tx(103.93, 104.80, "hero",   "RÉSURRECTION")
tx(104.90, 106.85, "tag",    "ISIS = MARIE")
tx(107.00, 109.85, "tag",    "HORUS = FILS DE DIEU")
tx(109.95, 111.50, "tag",    "ISSA = LE PROPHÈTE")
tx(113.50, 116.00, "hero",   "LE CULTE", sub="DE JÉSUS ?")
tx(116.12, 118.90, "chapter", "LA VÉRITÉ", sub="CHAPITRE IV", y=330)
tx(119.10, 123.80, "stamp",  "THÉORIE DÉMENTIE")
tx(131.00, 135.00, "stamp",  "AUCUNE PREUVE")
tx(135.25, 139.75, "hero",   "L'HISTOIRE", sub="DE L'AFRIQUE")
tx(142.80, 144.30, "hero",   "FICTIONS")
tx(144.60, DUR,    "end",    "OSIRIS", sub="MYTHE · THÉORIE · HISTOIRE")

# ---------------------------------------------------------------- transitions
# entre chaque scène : fondu enchaîné TR s, avec un flash lumineux sur les entrées de chapitre
FLASH_AT = [12.10, 70.02, 89.88, 116.06, 22.26, 95.50, 135.08, 142.30]

def build():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    words = json.load(open(os.path.join(root, "src", "data", "words.json"), encoding="utf-8"))
    spec = dict(fps=FPS, w=W, h=H, dur=DUR, voice_dur=VOICE_DUR, handle=HANDLE, tr=TR, cam_zoom=CAM_ZOOM,
                clips={k: dict(src=v[0], t=v[1], crop=v[2]) for k, v in CLIPS.items()},
                stills={k: dict(src=v[0], box=v[1]) for k, v in STILLS.items()},
                scenes=S, texts=T, flashes=FLASH_AT, captions=words)
    # contrôle de continuité
    for a, b in zip(S, S[1:]):
        assert abs(a["t1"] - b["t0"]) < 1e-6, (a["id"], b["id"])
    json.dump(spec, open(os.path.join(root, "src", "data", "timeline.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return spec

if __name__ == "__main__":
    s = build(); print(len(s["scenes"]), "scènes,", len(s["texts"]), "textes,", len(s["captions"]), "sous-titres")
