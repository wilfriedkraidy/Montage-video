/* Test hors After Effects : execute OSIRIS_AFTER_EFFECTS_2022.jsx dans Node avec un modele objet AE
   simule et STRICT (matchNames connus uniquement, dimensions des valeurs, ordre des cles...).
   Usage : node src/tests/ae_mock_test.js OSIRIS_AFTER_EFFECTS_2022.jsx                      */
var fs = require("fs"), path = require("path"), vm = require("vm");
var jsxPath = path.resolve(process.argv[2]);
var ROOT = path.dirname(jsxPath);
var stats = { comps: 0, layers: 0, keys: 0, effects: {}, errors: [] };

var PVT = { NO_VALUE: 0, ThreeD_SPATIAL: 1, ThreeD: 2, TwoD_SPATIAL: 3, TwoD: 4, OneD: 5, COLOR: 6, CUSTOM_VALUE: 7, MARKER: 8, LAYER_INDEX: 9, MASK_INDEX: 10, SHAPE: 11, TEXT_DOCUMENT: 12 };
function dimsOf(t) { return t === PVT.ThreeD_SPATIAL || t === PVT.ThreeD ? 3 : (t === PVT.TwoD_SPATIAL || t === PVT.TwoD ? 2 : (t === PVT.COLOR ? 4 : 1)); }

function Prop(matchName, type, owner) {
    this.matchName = matchName; this.name = matchName; this.propertyValueType = type; this.owner = owner;
    this.keys = []; this.value = type === PVT.TEXT_DOCUMENT ? new TextDocument("") : null; this.expression = "";
}
Prop.prototype.check = function (v) {
    var t = this.propertyValueType;
    if (t === PVT.TEXT_DOCUMENT) { if (!(v instanceof TextDocument)) throw new Error("TextDocument attendu"); return; }
    if (t === PVT.COLOR) { if (!Array.isArray(v) || (v.length !== 3 && v.length !== 4)) throw new Error(this.matchName + ": couleur invalide"); return; }
    var n = dimsOf(t);
    if (n === 1) { if (typeof v !== "number" || isNaN(v)) throw new Error(this.matchName + ": nombre attendu, recu " + JSON.stringify(v)); return; }
    if (!Array.isArray(v) || v.length !== n) throw new Error(this.matchName + ": " + n + " dimensions attendues, recu " + JSON.stringify(v));
    for (var i = 0; i < v.length; i++) if (typeof v[i] !== "number" || isNaN(v[i])) throw new Error(this.matchName + ": valeur non numerique");
};
Prop.prototype.setValue = function (v) { if (this.keys.length) throw new Error("setValue sur propriete animee"); this.check(v); this.value = v; };
Prop.prototype.setValuesAtTimes = function (ts, vs) {
    if (ts.length !== vs.length || !ts.length) throw new Error(this.matchName + ": longueurs temps/valeurs");
    for (var i = 0; i < ts.length; i++) {
        this.check(vs[i]);
        if (i && ts[i] <= ts[i - 1]) throw new Error(this.matchName + ": temps non croissants " + ts[i - 1] + " -> " + ts[i]);
        this.keys.push({ t: ts[i], v: vs[i] }); stats.keys++;
    }
};
Prop.prototype.setValueAtTime = function (t, v) { this.setValuesAtTimes([t], [v]); };
Object.defineProperty(Prop.prototype, "numKeys", { get: function () { return this.keys.length; } });
Prop.prototype.setTemporalEaseAtKey = function (k, a, b) {
    if (k < 1 || k > this.keys.length) throw new Error("index de cle");
    var t = this.propertyValueType, n = (t === PVT.TwoD) ? 2 : (t === PVT.ThreeD ? 3 : 1);
    if (a.length !== n || b.length !== n) throw new Error(this.matchName + ": KeyframeEase x" + n + " attendu, recu " + a.length);
};
Prop.prototype.setInterpolationTypeAtKey = function (k, a) { if (k < 1 || k > this.keys.length || a === undefined) throw new Error("interpolation"); };

function Group(matchName, schema, owner) {
    this.matchName = matchName; this.name = matchName; this.owner = owner; this.children = []; this.schema = schema || {};
    for (var m in this.schema.fixed || {}) this.children.push(make(m, this.schema.fixed[m], this));
}
function make(m, def, owner) { return (typeof def === "number") ? new Prop(m, def, owner) : new Group(m, def, owner); }
Group.prototype.property = function (key) {
    if (typeof key === "number") { if (key < 1 || key > this.children.length) throw new Error(this.matchName + ": index " + key + " hors limites"); return this.children[key - 1]; }
    for (var i = 0; i < this.children.length; i++) if (this.children[i].matchName === key || this.children[i].name === key) return this.children[i];
    throw new Error("Propriete inconnue '" + key + "' dans " + this.matchName);
};
Object.defineProperty(Group.prototype, "numProperties", { get: function () { return this.children.length; } });
Group.prototype.addProperty = function (m) {
    var add = this.schema.add || {};
    if (!(m in add)) throw new Error("addProperty('" + m + "') non autorise dans " + this.matchName);
    var g = make(m, add[m], this); this.children.push(g);
    if (this.matchName === "ADBE Effect Parade") stats.effects[m] = (stats.effects[m] || 0) + 1;
    return g;
};

var C = PVT.COLOR, O = PVT.OneD;
var EFFECTS = {
    "ADBE Gaussian Blur 2": { fixed: { "ADBE Gaussian Blur 2-0001": O, "ADBE Gaussian Blur 2-0002": O, "ADBE Gaussian Blur 2-0003": O } },
    "ADBE Drop Shadow": { fixed: { "ADBE Drop Shadow-0001": C, "ADBE Drop Shadow-0002": O, "ADBE Drop Shadow-0003": O, "ADBE Drop Shadow-0004": O, "ADBE Drop Shadow-0005": O, "ADBE Drop Shadow-0006": O } },
    "ADBE Glo2": { fixed: { "ADBE Glo2-0001": O, "ADBE Glo2-0002": O, "ADBE Glo2-0003": O, "ADBE Glo2-0004": O, "ADBE Glo2-0005": O } },
    "ADBE Linear Wipe": { fixed: { "ADBE Linear Wipe-0001": O, "ADBE Linear Wipe-0002": O, "ADBE Linear Wipe-0003": O } },
    "ADBE Ramp": { fixed: { "ADBE Ramp-0001": PVT.TwoD_SPATIAL, "ADBE Ramp-0002": C, "ADBE Ramp-0003": PVT.TwoD_SPATIAL, "ADBE Ramp-0004": C, "ADBE Ramp-0005": O, "ADBE Ramp-0006": O, "ADBE Ramp-0007": O } },
    "ADBE Noise": { fixed: { "ADBE Noise-0001": O, "ADBE Noise-0002": O, "ADBE Noise-0003": O } }
};
var SELECTOR = { fixed: { "ADBE Text Index Start": O, "ADBE Text Index End": O, "ADBE Text Percent Start": O, "ADBE Text Percent End": O,
    "ADBE Text Range Advanced": { fixed: { "ADBE Text Range Units": O, "ADBE Text Range Type2": O } } } };
var ANIMATOR = { fixed: { "ADBE Text Selectors": { add: { "ADBE Text Selector": SELECTOR } },
    "ADBE Text Animator Properties": { add: { "ADBE Text Tracking Amount": O, "ADBE Text Fill Color": C } } } };
var VGROUP = { fixed: { "ADBE Vectors Group": { add: {
    "ADBE Vector Shape - Rect": { fixed: { "ADBE Vector Rect Size": PVT.TwoD } },
    "ADBE Vector Shape - Ellipse": { fixed: { "ADBE Vector Ellipse Size": PVT.TwoD } },
    "ADBE Vector Graphic - Stroke": { fixed: { "ADBE Vector Stroke Color": C, "ADBE Vector Stroke Width": O } },
    "ADBE Vector Graphic - Fill": { fixed: { "ADBE Vector Fill Color": C } } } } } };

function Layer(comp, kind, src) {
    stats.layers++;
    this.comp = comp; this.kind = kind; this.source = src; this.name = kind; this.startTime = 0;
    this._in = 0; this._out = comp.duration; this.parent = null; this.adjustmentLayer = false; this.blendingMode = 0;
    var self = this; this._3d = false;
    var T = new Group("ADBE Transform Group", { fixed: {} }, this);
    this.T = T;
    this._build2D();
    var fx = new Group("ADBE Effect Parade", { add: EFFECTS }, this);
    this.groups = [T, fx];
    if (kind === "text") this.groups.push(new Group("ADBE Text Properties", { fixed: { "ADBE Text Document": PVT.TEXT_DOCUMENT, "ADBE Text Animators": { add: { "ADBE Text Animator": ANIMATOR } } } }, this));
    if (kind === "shape") this.groups.push(new Group("ADBE Root Vectors Group", { add: { "ADBE Vector Group": VGROUP } }, this));
    if (kind === "camera") this.groups.push(new Group("ADBE Camera Options Group", { fixed: { "ADBE Camera Zoom": O } }, this));
    if (kind === "camera") { this._3d = true; this._build3D(); }
    if (src && src.duration !== undefined && !src.isStill) this._out = Math.min(comp.duration, src.duration);
}
Layer.prototype._build2D = function () {
    var T = this.T; T.children = [];
    var defs = { "ADBE Anchor Point": PVT.TwoD_SPATIAL, "ADBE Position": PVT.TwoD_SPATIAL, "ADBE Position_0": O, "ADBE Position_1": O,
        "ADBE Scale": PVT.ThreeD, "ADBE Rotate Z": O, "ADBE Opacity": O };
    for (var m in defs) T.children.push(new Prop(m, defs[m], T));
};
Layer.prototype._build3D = function () {
    var T = this.T; T.children = [];
    var defs = { "ADBE Anchor Point": PVT.ThreeD_SPATIAL, "ADBE Position": PVT.ThreeD_SPATIAL, "ADBE Position_0": O, "ADBE Position_1": O, "ADBE Position_2": O,
        "ADBE Scale": PVT.ThreeD, "ADBE Rotate X": O, "ADBE Rotate Y": O, "ADBE Rotate Z": O, "ADBE Opacity": O };
    for (var m in defs) T.children.push(new Prop(m, defs[m], T));
    var P = T.property("ADBE Position");
    Object.defineProperty(P, "dimensionsSeparated", { get: function () { return this._sep || false; }, set: function (v) { this._sep = v; } });
};
Object.defineProperty(Layer.prototype, "threeDLayer", { get: function () { return this._3d; }, set: function (v) {
    if (this.kind === "text" || this.kind === "footage" || this.kind === "comp" || this.kind === "solid") { if (v && !this._3d) { this._3d = true; this._build3D(); } }
    else if (v) throw new Error("threeDLayer non supporte pour " + this.kind);
} });
Object.defineProperty(Layer.prototype, "inPoint", { get: function () { return this._in; }, set: function (v) { if (typeof v !== "number" || isNaN(v)) throw new Error("inPoint"); this._in = v; } });
Object.defineProperty(Layer.prototype, "outPoint", { get: function () { return this._out; }, set: function (v) { if (typeof v !== "number" || v <= this._in) throw new Error("outPoint <= inPoint"); this._out = v; } });
Layer.prototype.property = function (m) {
    for (var i = 0; i < this.groups.length; i++) if (this.groups[i].matchName === m) return this.groups[i];
    throw new Error("Groupe inconnu " + m + " sur calque " + this.kind);
};
Object.defineProperty(Layer.prototype, "transform", { get: function () { return this.T; } });

function Layers(comp) { this.comp = comp; this.list = []; }
Layers.prototype._push = function (L) { this.list.unshift(L); return L; };
Layers.prototype.add = function (item) { if (!item || !(item instanceof FootageItem || item instanceof CompItem)) throw new Error("layers.add : item invalide"); return this._push(new Layer(this.comp, item instanceof CompItem ? "comp" : "footage", item)); };
Layers.prototype.addSolid = function (c, n, w, h, pa, d) { if (c.length !== 3 || !(w > 0) || !(h > 0) || !(d > 0)) throw new Error("addSolid args"); return this._push(new Layer(this.comp, "solid")); };
Layers.prototype.addNull = function (d) { return this._push(new Layer(this.comp, "null")); };
Layers.prototype.addCamera = function (n, c) { if (c.length !== 2) throw new Error("addCamera"); return this._push(new Layer(this.comp, "camera")); };
Layers.prototype.addText = function (s) { if (typeof s !== "string") throw new Error("addText"); var L = new Layer(this.comp, "text"); L.property("ADBE Text Properties").property("ADBE Text Document").value = new TextDocument(s); return this._push(L); };
Layers.prototype.addShape = function () { return this._push(new Layer(this.comp, "shape")); };

function Item() { this.parentFolder = null; }
function FolderItem(n) { this.name = n; }
function FootageItem(f) { this.file = f; this.name = path.basename(f); this.isStill = /\.png$/i.test(f); this.duration = this.isStill ? 0 : 1e9;
    this.mainSource = { hasAlpha: /\.png$/i.test(f), alphaMode: 0, isStill: this.isStill }; }
function CompItem(n, w, h, pa, d, fps) {
    if (!(w >= 4 && w <= 30000 && h >= 4 && h <= 30000 && d > 0 && d <= 10800 && fps > 0)) throw new Error("addComp args invalides " + [n, w, h, d, fps]);
    if (w % 1 || h % 1) throw new Error("addComp : dimensions entieres requises");
    this.name = n; this.width = w; this.height = h; this.duration = d; this.frameRate = fps; this.layers = new Layers(this); stats.comps++;
}
CompItem.prototype.openInViewer = function () { };
function TextDocument(s) { this.text = s; this.font = "ArialMT"; this.fontSize = 36; this.fillColor = [1, 1, 1]; }
TextDocument.prototype.resetCharStyle = function () { };
var project = {
    items: { addFolder: function (n) { return new FolderItem(n); }, addComp: function (n, w, h, pa, d, fps) { return new CompItem(n, w, h, pa, d, fps); } },
    importFile: function (io) { if (!fs.existsSync(io.file.fsName)) throw new Error("fichier absent"); return new FootageItem(io.file.fsName); },
    renderQueue: { items: { add: function (c) { return { outputModule: function () { return {}; } }; } } },
    save: function (f) { stats.saved = f.fsName; }
};
function File(p) { if (!(this instanceof File)) return new File(p); this.fsName = path.resolve(p); this.exists = fs.existsSync(this.fsName);
    this.parent = { fsName: path.dirname(this.fsName) }; }
var ctx = {
    $: { fileName: jsxPath }, File: File, alert: function (m) { stats.alert = m; },
    app: { version: "22.6.0x61", project: project, newProject: function () { return project; }, beginUndoGroup: function () { }, endUndoGroup: function () { } },
    ImportOptions: function (f) { this.file = f; this.canImportAs = function () { return true; }; },
    ImportAsType: { FOOTAGE: 1 }, AlphaMode: { STRAIGHT: 1 }, PropertyValueType: PVT,
    KeyframeEase: function (s, i) { if (i < 0.1 || i > 100) throw new Error("influence"); this.speed = s; this.influence = i; },
    KeyframeInterpolationType: { LINEAR: 6612, BEZIER: 6613, HOLD: 6614 }, ParagraphJustification: { CENTER_JUSTIFY: 7415 },
    BlendingMode: { ADD: 5220, SCREEN: 5224 }, TextDocument: TextDocument
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(jsxPath, "utf8"), ctx, { filename: jsxPath });
console.log("compositions:", stats.comps, "| calques:", stats.layers, "| cles:", stats.keys);
console.log("effets:", JSON.stringify(stats.effects));
console.log("projet enregistre:", stats.saved ? path.basename(stats.saved) : "NON");
console.log("ALERT >>>", stats.alert);
process.exit(/avertissement/.test(stats.alert || "") ? 1 : 0);
