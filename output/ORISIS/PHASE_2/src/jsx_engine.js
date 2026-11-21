/*  OSIRIS - Phase 2 - Motion design
    Script ExtendScript pour Adobe After Effects 2022 (v22.x) - compatible ES3.

    UTILISATION
      1. Installer les polices du dossier media/fonts (Cinzel, Montserrat) puis redemarrer AE.
      2. Garder ce fichier a cote du dossier "media" (structure livree).
      3. AE > Fichier > Scripts > Executer le fichier de script... > OSIRIS_AFTER_EFFECTS_2022.jsx
         (Preferences > Scripts et expressions > "Autoriser les scripts a ecrire des fichiers" coche).
      Le script importe les medias, construit toutes les compositions (scenes 2.5D, camera,
      titres animes, sous-titres karaoke, eclairs, grain, audio), ajoute OSIRIS_FINAL a la file de
      rendu et enregistre le projet OSIRIS_FINAL.aep a cote du script.
    Genere automatiquement par src/make_jsx.py a partir de src/data/timeline.json.
*/
(function OSIRIS_BUILD() {
    var DATA = /*__DATA__*/null;

    var ROOT = File($.fileName).parent;
    var MEDIA = ROOT.fsName + "/media/";
    var warnings = [];
    function warn(msg) { warnings.push(msg); }

    if (parseFloat(app.version) < 22) {
        alert("OSIRIS : ce script est prevu pour After Effects 2022 (v22) ou plus recent.\nVersion detectee : " + app.version);
    }
    app.beginUndoGroup("OSIRIS - construction du projet");
    var proj = app.project ? app.project : app.newProject();

    /* ---------------------------------------------------------------- dossiers + import */
    var fRoot = proj.items.addFolder("OSIRIS");
    var fMedia = proj.items.addFolder("01_MEDIAS"); fMedia.parentFolder = fRoot;
    var fComps = proj.items.addFolder("02_PRECOMPS"); fComps.parentFolder = fRoot;
    var FOOT = {};
    var i, j, k;
    for (i = 0; i < DATA.footage.length; i++) {
        var rel = DATA.footage[i];
        var f = new File(MEDIA + rel);
        if (!f.exists) { warn("Media manquant : " + rel); continue; }
        try {
            var io = new ImportOptions(f);
            if (io.canImportAs(ImportAsType.FOOTAGE)) { io.importAs = ImportAsType.FOOTAGE; }
            var it = proj.importFile(io);
            it.parentFolder = fMedia;
            if (it.mainSource && it.mainSource.hasAlpha) {
                it.mainSource.alphaMode = AlphaMode.STRAIGHT;
            }
            FOOT[rel] = it;
        } catch (e) { warn("Import impossible : " + rel + " (" + e.toString() + ")"); }
    }

    /* ---------------------------------------------------------------- utilitaires */
    function isKeys(v) { return v !== null && typeof v === "object" && !(v instanceof Array) && v.t !== undefined; }

    function easeAll(p) {
        var n = 1, vt = p.propertyValueType;
        if (vt === PropertyValueType.TwoD) { n = 2; } else if (vt === PropertyValueType.ThreeD) { n = 3; }
        var e = [], q;
        for (q = 0; q < n; q++) { e.push(new KeyframeEase(0, 33.33)); }
        for (q = 1; q <= p.numKeys; q++) {
            try { p.setTemporalEaseAtKey(q, e, e); } catch (err) { }
        }
    }

    function fixDim(p, v) {
        /* adapte la dimension d'une valeur a la propriete (ex. echelle 2D -> 3 valeurs) */
        var vt = p.propertyValueType;
        if (typeof v === "number") {
            if (vt === PropertyValueType.ThreeD || vt === PropertyValueType.ThreeD_SPATIAL) { return [v, v, v]; }
            if (vt === PropertyValueType.TwoD || vt === PropertyValueType.TwoD_SPATIAL) { return [v, v]; }
            return v;
        }
        if (!(v instanceof Array)) { return v; }
        var out = v.slice(0);
        if (vt === PropertyValueType.ThreeD || vt === PropertyValueType.ThreeD_SPATIAL) {
            while (out.length < 3) { out.push(out.length === 2 && p.matchName === "ADBE Scale" ? out[0] : 0); }
        } else if (vt === PropertyValueType.TwoD || vt === PropertyValueType.TwoD_SPATIAL) {
            out = [out[0], out[1]];
        }
        return out;
    }

    function setP(p, v) {
        if (v === undefined || v === null || !p) { return; }
        try {
            if (isKeys(v)) {
                var vals = [];
                for (var q = 0; q < v.v.length; q++) { vals.push(fixDim(p, v.v[q])); }
                p.setValuesAtTimes(v.t, vals);
                if (v.e === "ease") { easeAll(p); }
                if (v.e === "hold") {
                    for (q = 1; q <= p.numKeys; q++) { p.setInterpolationTypeAtKey(q, KeyframeInterpolationType.HOLD); }
                }
                if (v.e === "linear") {
                    for (q = 1; q <= p.numKeys; q++) {
                        try { p.setInterpolationTypeAtKey(q, KeyframeInterpolationType.LINEAR); } catch (e1) { }
                    }
                }
            } else {
                p.setValue(fixDim(p, v));
            }
        } catch (e) { warn("Propriete " + p.name + " : " + e.toString()); }
    }

    function tr(L, m) { return L.property("ADBE Transform Group").property(m); }

    function addFx(L, list) {
        if (!list) { return; }
        for (var q = 0; q < list.length; q++) {
            var spec = list[q], fx;
            try {
                fx = L.property("ADBE Effect Parade").addProperty(spec.m);
            } catch (e) { warn("Effet indisponible " + spec.m + " sur " + L.name); continue; }
            var key;
            if (spec.p) { for (key in spec.p) { if (spec.p.hasOwnProperty(key)) { try { fx.property(key).setValue(spec.p[key]); } catch (e2) { warn(spec.m + "/" + key + " : " + e2.toString()); } } } }
            if (spec.k) { for (key in spec.k) { if (spec.k.hasOwnProperty(key)) { setP(fx.property(key), spec.k[key]); } } }
        }
    }

    function makeText(comp, s) {
        var L = comp.layers.addText(s.text);
        var tp = L.property("ADBE Text Properties").property("ADBE Text Document");
        var td = tp.value;
        try { td.resetCharStyle(); } catch (e0) { }
        try { td.font = s.font; } catch (e1) { warn("Police " + s.font + " non installee"); }
        td.fontSize = s.size;
        td.applyFill = true;
        td.fillColor = s.fill;
        if (s.stroke) {
            td.applyStroke = true; td.strokeColor = s.stroke.c; td.strokeWidth = s.stroke.w; td.strokeOverFill = false;
        } else { td.applyStroke = false; }
        td.tracking = s.track || 0;
        if (s.lead) { try { td.autoLeading = false; td.leading = s.lead; } catch (e2) { } }
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.setValue(td);
        L.name = s.name;
        return L;
    }

    function textAnimTracking(L, keys) {
        var anims = L.property("ADBE Text Properties").property("ADBE Text Animators");
        anims.addProperty("ADBE Text Animator");
        var an = anims.property(anims.numProperties);
        an.name = "Approche";
        an.property("ADBE Text Animator Properties").addProperty("ADBE Text Tracking Amount");
        an = anims.property(anims.numProperties);
        setP(an.property("ADBE Text Animator Properties").property("ADBE Text Tracking Amount"), keys);
    }

    function textAnimHighlight(L, hl, color) {
        /* karaoke : couleur or sur le mot prononce (selecteur de plage par index de mots, cles maintenues) */
        var anims = L.property("ADBE Text Properties").property("ADBE Text Animators");
        anims.addProperty("ADBE Text Animator");
        var an = anims.property(anims.numProperties);
        an.name = "Mot actif";
        an.property("ADBE Text Animator Properties").addProperty("ADBE Text Fill Color");
        an = anims.property(anims.numProperties);
        an.property("ADBE Text Animator Properties").property("ADBE Text Fill Color").setValue(color);
        var sels = an.property("ADBE Text Selectors");
        if (sels.numProperties < 1) { sels.addProperty("ADBE Text Selector"); }
        an = anims.property(anims.numProperties);
        var sel = an.property("ADBE Text Selectors").property(1);
        var adv = sel.property("ADBE Text Range Advanced");
        adv.property("ADBE Text Range Units").setValue(2);   /* index */
        adv.property("ADBE Text Range Type2").setValue(3);   /* mots */
        sel = anims.property(anims.numProperties).property("ADBE Text Selectors").property(1);
        setP(sel.property("ADBE Text Index Start"), { t: hl.t, v: hl.start, e: "hold" });
        setP(sel.property("ADBE Text Index End"), { t: hl.t, v: hl.end, e: "hold" });
    }

    function makeShape(comp, s) {
        var L = comp.layers.addShape();
        L.name = s.name;
        var root = L.property("ADBE Root Vectors Group");
        function group(shapeMatch, sizeMatch, size, paint, color, width) {
            root = L.property("ADBE Root Vectors Group");
            root.addProperty("ADBE Vector Group");
            var g = root.property(root.numProperties);
            g.property("ADBE Vectors Group").addProperty(shapeMatch);
            g = root.property(root.numProperties);
            g.property("ADBE Vectors Group").property(1).property(sizeMatch).setValue(size);
            g.property("ADBE Vectors Group").addProperty(paint);
            g = root.property(root.numProperties);
            var pt = g.property("ADBE Vectors Group").property(2);
            if (paint === "ADBE Vector Graphic - Stroke") {
                pt.property("ADBE Vector Stroke Color").setValue(color);
                pt.property("ADBE Vector Stroke Width").setValue(width);
            } else {
                pt.property("ADBE Vector Fill Color").setValue(color);
            }
        }
        if (s.type === "rect") {
            group("ADBE Vector Shape - Rect", "ADBE Vector Rect Size", [s.w, s.h], "ADBE Vector Graphic - Stroke", s.stroke, s.sw);
        } else {
            group("ADBE Vector Shape - Ellipse", "ADBE Vector Ellipse Size", [s.r * 4.4, s.r * 4.4], "ADBE Vector Graphic - Stroke", s.ring, 3);
            group("ADBE Vector Shape - Ellipse", "ADBE Vector Ellipse Size", [s.r * 2, s.r * 2], "ADBE Vector Graphic - Fill", s.fill, 0);
        }
        return L;
    }

    /* ---------------------------------------------------------------- construction */
    var COMPS = {};
    function buildLayer(comp, s, made) {
        var L = null;
        switch (s.type) {
            case "footage":
                if (!FOOT[s.src]) { warn("Calque ignore (media absent) : " + s.src); return null; }
                L = comp.layers.add(FOOT[s.src]); break;
            case "comp":
                L = comp.layers.add(COMPS[s.src]); break;
            case "solid":
                L = comp.layers.addSolid(s.color, s.name, s.w, s.h, 1, comp.duration); break;
            case "adjustment":
                L = comp.layers.addSolid([1, 1, 1], s.name, comp.width, comp.height, 1, comp.duration);
                L.adjustmentLayer = true; break;
            case "null":
                L = comp.layers.addNull(comp.duration); break;
            case "camera":
                L = comp.layers.addCamera("Camera 2.5D", [comp.width / 2, comp.height / 2]);
                L.property("ADBE Camera Options Group").property("ADBE Camera Zoom").setValue(s.zoom);
                tr(L, "ADBE Position").setValue([comp.width / 2, comp.height / 2, -s.zoom]);
                tr(L, "ADBE Anchor Point").setValue([comp.width / 2, comp.height / 2, 0]);
                return L;
            case "text":
                L = makeText(comp, s); break;
            case "rect":
            case "ellipse":
                L = makeShape(comp, s); break;
        }
        if (!L) { return null; }
        if (s.name) { try { L.name = s.name; } catch (e0) { } }
        if (s.start !== undefined) { L.startTime = s.start; }
        if (s.threeD) { L.threeDLayer = true; }
        if (s.parent) { L.parent = made[s.parent - 1]; }
        if (s.blend === "ADD") { L.blendingMode = BlendingMode.ADD; }
        if (s.anchor) { setP(tr(L, "ADBE Anchor Point"), s.anchor); }
        if (s.pos) { setP(tr(L, "ADBE Position"), s.pos); }
        if (s.posKeys) { setP(tr(L, "ADBE Position"), s.posKeys); }
        if (s.pos3 || s.posX || s.posY || s.posZ) {
            var P = tr(L, "ADBE Position");
            P.dimensionsSeparated = true;
            var base = s.pos3 || [comp.width / 2, comp.height / 2, 0];
            setP(tr(L, "ADBE Position_0"), s.posX ? s.posX : base[0]);
            setP(tr(L, "ADBE Position_1"), s.posY ? s.posY : base[1]);
            setP(tr(L, "ADBE Position_2"), s.posZ ? s.posZ : (base[2] === null ? 0 : base[2]));
        }
        if (s.scale !== undefined) {
            var sc = s.scale;
            if (typeof sc === "number") { sc = [sc, sc]; }
            setP(tr(L, "ADBE Scale"), sc);
        }
        if (s.scale3 !== undefined) { setP(tr(L, "ADBE Scale"), [s.scale3, s.scale3, s.scale3]); }
        if (s.rot !== undefined) { setP(tr(L, "ADBE Rotate Z"), s.rot); }
        if (s.rotX) { setP(tr(L, "ADBE Rotate X"), s.rotX); }
        if (s.rotY) { setP(tr(L, "ADBE Rotate Y"), s.rotY); }
        if (s.opacity !== undefined) { setP(tr(L, "ADBE Opacity"), s.opacity); }
        if (s.expr) { try { tr(L, "ADBE Scale").expression = s.expr; } catch (e3) { warn("Expression : " + e3.toString()); } }
        if (s.type === "text") {
            if (s.trackKeys) { textAnimTracking(L, s.trackKeys); }
            if (s.hl) { textAnimHighlight(L, s.hl, s.hlColor); }
            if (s.glow) { addFx(L, [{ m: "ADBE Glo2", p: { "ADBE Glo2-0003": 28, "ADBE Glo2-0004": 0.7 } }]); }
            if (s.shadow) { addFx(L, [{ m: "ADBE Drop Shadow", p: { "ADBE Drop Shadow-0004": 6, "ADBE Drop Shadow-0005": 22 } }]); }
        }
        addFx(L, s.fx);
        try {
            var inP = s["in"] !== undefined ? s["in"] : s.inP;
            if (inP !== undefined) { L.inPoint = inP; }
            if (s.out !== undefined) { L.outPoint = s.out; }
        } catch (e4) { warn("In/Out " + L.name + " : " + e4.toString()); }
        return L;
    }

    var main = null;
    for (i = 0; i < DATA.comps.length; i++) {
        var cs = DATA.comps[i];
        var c = proj.items.addComp(cs.id, cs.w, cs.h, 1, cs.dur, DATA.comp.fps);
        c.bgColor = [0, 0, 0];
        c.parentFolder = (cs.id === DATA.main) ? fRoot : fComps;
        COMPS[cs.id] = c;
        var made = [];
        for (j = 0; j < cs.layers.length; j++) {
            try { made.push(buildLayer(c, cs.layers[j], made)); }
            catch (e) { made.push(null); warn(cs.id + " / calque " + (j + 1) + " : " + e.toString() + " (ligne " + e.line + ")"); }
        }
        if (cs.id === DATA.main) { main = c; }
    }

    /* ---------------------------------------------------------------- rendu + sauvegarde */
    if (main) {
        main.openInViewer();
        try {
            var rq = proj.renderQueue.items.add(main);
            rq.outputModule(1).file = new File(ROOT.fsName + "/OSIRIS_FINAL_AE.mov");
        } catch (e5) { warn("File de rendu : " + e5.toString()); }
    }
    app.endUndoGroup();
    try { proj.save(new File(ROOT.fsName + "/OSIRIS_FINAL.aep")); } catch (e6) { warn("Sauvegarde .aep : " + e6.toString()); }

    var msg = "OSIRIS : projet construit (" + DATA.comps.length + " compositions).";
    if (warnings.length) { msg += "\n\n" + warnings.length + " avertissement(s) :\n" + warnings.slice(0, 25).join("\n"); }
    alert(msg);
})();
