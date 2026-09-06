"""Build the validity-audit page: every item as a 1:1 crop in cell x level tables, with per-rater flags.

Usage: python make_audit.py v1 [out_html]
Writes gen/out/<name>/audit.html (and a copy to out_html if given). Images are embedded, so the page is self-contained.
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

from PIL import Image

from render import GEN, H, W

CELL_NAMES = {
    "c01_base": ("1", "Base", "EN text, mid-word cut, border"),
    "c02_bar": ("2", "Solid bar", "saliency anchor, same box as cell 1"),
    "c03_matched": ("3", "Matched bar", "skyline blobs, ink and height matched per glyph"),
    "c04_gibberish": ("4", "Gibberish", "letters shuffled within each word"),
    "c05_wordgap": ("5", "Word-gap", "final word falls outside after a space"),
    "c06_decoy": ("6", "Decoy", "separate label outside the box, all negatives by definition"),
    "c07_pill": ("7", "Pill", "capsule, filled, no line"),
    "c08_fill": ("8", "Fill boundary", "tinted box, no border line"),
    "c09_bottom": ("9", "Bottom spill", "paragraph, last line crosses the bottom edge"),
    "c10_thai": ("10", "Thai base", "single line, no spaces"),
    "c11_marks": ("11", "Thai marks", "tone marks, upper vowels, below vowels cross the top or bottom edge"),
    "c12_thaiwrap": ("12", "Thai wrap", "wrapped paragraph, last line crosses the bottom edge"),
}
LEVEL_ORDER = {
    "default": ["anchor", "m10", "m3", "p4", "p12", "p30"],
    "c05_wordgap": ["anchor", "m10", "m3", "short", "medium", "long"],
    "c06_decoy": ["incomplete_gTwin", "incomplete_g12", "incomplete_g30", "complete_gTwin", "complete_g12", "complete_g30"],
    "c07_pill": ["anchor", "m10", "m3", "corner", "p4", "p12"],
    "c11_marks": ["anchor", "m3", "m1", "p3", "p6", "p9"],
}
LEVEL_NAMES = {
    "anchor": "anchor, easy fit", "m10": "−10 px", "m3": "−3 px", "m1": "−1 px",
    "p3": "+3 px", "p4": "+4 px", "p6": "+6 px", "p9": "+9 px", "p12": "+12 px", "p30": "+30 px",
    "short": "outside word: short", "medium": "outside word: medium", "long": "outside word: long",
    "corner": "corner-cross, inside the bounding box",
    "incomplete_gTwin": "incomplete phrase · gap ≈4 px", "incomplete_g12": "incomplete phrase · gap 12 px",
    "incomplete_g30": "incomplete phrase · gap 30 px", "complete_gTwin": "complete phrase · gap ≈4 px",
    "complete_g12": "complete phrase · gap 12 px", "complete_g30": "complete phrase · gap 30 px",
}


def crop_b64(r) -> tuple[str, int, int]:
    bx, by, bw, bh = r["geo"]; il, it, ir, ib = r["ink_bbox"]
    x0, y0 = max(min(bx, il) - 14, 0), max(min(by, it) - 10, 0)
    x1, y1 = min(max(bx + bw, ir + 1) + 14, W), min(max(by + bh, ib + 1) + 10, H)
    im = Image.open(r["path"]).crop((x0, y0, x1, y1))
    b = io.BytesIO(); im.save(b, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode(), im.width, im.height


def note_field(note: str, key: str):
    for part in note.split(";"):
        if part.startswith(key + "="):
            return part.split("=", 1)[1]
    return ""


def main(name: str, extra_out: str | None):
    out = GEN / "out" / name
    recs = [json.loads(l) for l in (out / "manifest.jsonl").open(encoding="utf-8")]
    items = []
    for r in recs:
        src, w, h = crop_b64(r)
        c = r["cert"]
        items.append({
            "id": Path(r["path"]).stem, "cell": r["cell"], "level": r["level"], "sid": r["sid"], "label": r["label"],
            "ov": c["overflow_px"], "pen": c["penetration"], "clr": c["clearance"], "eye7": r["eye768"], "eye5": r["eye512"],
            "sub": bool(r["sub_resolution"]), "weak": r["label"] == "yes" and c["overflow_px"] < 6,
            "family": note_field(r["note"], "family"), "hclr": c.get("h_clearance"), "gap": c.get("min_gap", c.get("gap")),
            "font": r.get("font", ""), "fs": r.get("fs", ""), "src": src, "w": w, "h": h,
        })
    cells = []
    for cell, (num, title, blurb) in CELL_NAMES.items():
        order = LEVEL_ORDER.get(cell, LEVEL_ORDER["default"])
        cells.append({"cell": cell, "num": num, "title": title, "blurb": blurb, "levels": order})
    page = (TEMPLATE.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
            .replace("__CELLS__", json.dumps(cells, ensure_ascii=False))
            .replace("__LEVEL_NAMES__", json.dumps(LEVEL_NAMES, ensure_ascii=False))
            .replace("__SET__", name).replace("__N__", f"{len(items):,}"))
    (out / "audit.html").write_text(page, encoding="utf-8")
    if extra_out:
        Path(extra_out).write_text(page, encoding="utf-8")
    print(out / "audit.html", len(items), "items,", f"{len(page) / 1e6:.1f} MB")


TEMPLATE = r"""<meta charset="utf-8"><title>Does the Text Fit? Audit</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --bg:#f3f4f7; --surface:#ffffff; --surface-2:#e9ebf0; --line:#d5d9e2; --line-strong:#aeb5c4;
  --ink:#171a21; --ink-2:#4b5262; --ink-3:#7a8194;
  --accent:#1d5b8f; --accent-ink:#ffffff;
  --yes-bg:#fdf0d5; --yes-ink:#8a4b00; --yes-line:#e6b96a;
  --no-bg:#e3f2e7; --no-ink:#1f6b3a; --no-line:#8fc9a3;
  --wrong:#b3261e; --wrong-bg:#fbe9e7; --unsure:#9a6400; --unsure-bg:#fff4d6;
  --ok:#2e7d4f; --focus:#1d5b8f;
  --shadow:0 12px 40px rgba(20,24,40,.25);
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --bg:#14161b; --surface:#1c1f26; --surface-2:#252932; --line:#333845; --line-strong:#4a5162;
  --ink:#e8eaf0; --ink-2:#b4bac8; --ink-3:#7f869a;
  --accent:#6fb0e6; --accent-ink:#0f1a26;
  --yes-bg:#3a2a10; --yes-ink:#f1c27a; --yes-line:#7a5a22;
  --no-bg:#15301f; --no-ink:#8fd6a8; --no-line:#2f6a44;
  --wrong:#ff8a80; --wrong-bg:#3a1c1a; --unsure:#f2c14e; --unsure-bg:#3a2f10;
  --ok:#7fd39a; --focus:#6fb0e6; --shadow:0 12px 40px rgba(0,0,0,.6);
}}
:root[data-theme="dark"]{
  --bg:#14161b; --surface:#1c1f26; --surface-2:#252932; --line:#333845; --line-strong:#4a5162;
  --ink:#e8eaf0; --ink-2:#b4bac8; --ink-3:#7f869a;
  --accent:#6fb0e6; --accent-ink:#0f1a26;
  --yes-bg:#3a2a10; --yes-ink:#f1c27a; --yes-line:#7a5a22;
  --no-bg:#15301f; --no-ink:#8fd6a8; --no-line:#2f6a44;
  --wrong:#ff8a80; --wrong-bg:#3a1c1a; --unsure:#f2c14e; --unsure-bg:#3a2f10;
  --ok:#7fd39a; --focus:#6fb0e6; --shadow:0 12px 40px rgba(0,0,0,.6);
}
*{box-sizing:border-box}
[hidden]{display:none !important}
html{scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){ html{scroll-behavior:auto} }
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 "IBM Plex Sans",system-ui,sans-serif}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
h1,h2,h3{font-family:Archivo,"IBM Plex Sans",sans-serif;text-wrap:balance;margin:0}
button,input,select{font:inherit;color:inherit}
button{background:var(--surface);border:1px solid var(--line-strong);border-radius:6px;padding:5px 10px;cursor:pointer}
button:hover{border-color:var(--accent)}
button:focus-visible,input:focus-visible,.crop:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
input[type=text]{background:var(--surface);border:1px solid var(--line-strong);border-radius:6px;padding:5px 8px}

/* top bar */
.top{position:sticky;top:0;z-index:20;background:var(--surface);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:18px;padding:10px 20px;flex-wrap:wrap}
.top h1{font-size:17px;font-weight:600}
.top .sub{color:var(--ink-3);font-size:12.5px;margin-left:10px}
.top label{display:flex;align-items:center;gap:6px;color:var(--ink-2)}
.top .status{color:var(--ink-3);font-size:12px;margin-left:auto}
.top .status.live{color:var(--ok)}

.wrap{display:grid;grid-template-columns:230px minmax(0,1fr);gap:0}
@media (max-width:900px){.wrap{grid-template-columns:1fr}.rail{display:none}}

/* rail */
.rail{position:sticky;top:53px;height:calc(100vh - 53px);overflow-y:auto;border-right:1px solid var(--line);padding:14px 12px 30px;background:var(--surface)}
.rail .cell{margin-bottom:10px}
.rail .cell a{display:block;font-weight:600;font-size:13px;color:var(--ink);text-decoration:none;padding:3px 4px}
.rail .cell a:hover{color:var(--accent)}
.rail .chips{display:flex;flex-wrap:wrap;gap:4px;padding:0 4px}
.chip{display:inline-flex;align-items:center;gap:4px;font-size:11.5px;padding:2px 7px;border-radius:999px;border:1px solid var(--line);background:var(--surface-2);color:var(--ink-2);text-decoration:none;cursor:pointer}
.chip.done{border-color:var(--ok);color:var(--ok)}
.chip .n{font-family:"IBM Plex Mono",monospace;color:var(--wrong)}
.rail .tot{font-size:12px;color:var(--ink-3);padding:0 4px 10px;border-bottom:1px solid var(--line);margin-bottom:12px}

/* main */
main{padding:20px 28px 80px;min-width:0}
.intro{max-width:72ch;margin-bottom:22px}
.intro h2{font-size:22px;font-weight:600;margin-bottom:8px}
.intro p{margin:0 0 10px;color:var(--ink-2)}
.intro .keys{display:flex;flex-wrap:wrap;gap:6px 14px;color:var(--ink-3);font-size:12.5px}
kbd{font-family:"IBM Plex Mono",monospace;font-size:11.5px;border:1px solid var(--line-strong);border-bottom-width:2px;border-radius:4px;padding:0 5px;background:var(--surface)}
.attention{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin-bottom:26px;max-width:80ch}
.attention h3{font-size:14px;font-weight:600;margin-bottom:6px}
.attention ul{margin:0;padding-left:18px;color:var(--ink-2)}
.attention a{color:var(--accent)}

.cellhead{margin:34px 0 8px;display:flex;align-items:baseline;gap:12px}
.cellhead h2{font-size:20px;font-weight:600}
.cellhead .num{font-family:"IBM Plex Mono",monospace;color:var(--ink-3);font-size:13px}
.cellhead .blurb{color:var(--ink-3);font-size:13px}

.tbl{background:var(--surface);border:1px solid var(--line);border-radius:8px;margin-bottom:16px;overflow:hidden}
.tbl header{display:flex;align-items:center;gap:12px;padding:8px 14px;border-bottom:1px solid var(--line);background:var(--surface-2)}
.tbl header h3{font-size:14px;font-weight:600}
.tbl header .exp{font-size:12.5px;color:var(--ink-2)}
.tbl header .cnt{margin-left:auto;font-size:12px;color:var(--ink-3)}
.tbl header button{padding:3px 9px;font-size:12.5px}
.tbl header button.done{border-color:var(--ok);color:var(--ok)}
.rows{display:block}
.row{display:grid;grid-template-columns:120px minmax(0,1fr) 62px 190px 230px;gap:0 12px;align-items:center;padding:6px 14px;border-top:1px solid var(--line)}
.row:first-child{border-top:0}
.row.f-wrong{background:var(--wrong-bg)}
.row.f-unsure{background:var(--unsure-bg)}
.row .sid{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-2)}
.row .sid small{display:block;color:var(--ink-3);font-size:11px}
.row .cropwrap{overflow-x:auto;padding:2px 0}
.crop{display:block;border:1px solid var(--line);cursor:zoom-in;background:#fff;image-rendering:auto}
.badge{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:500;padding:2px 8px;border-radius:4px;border:1px solid}
.badge.yes{background:var(--yes-bg);color:var(--yes-ink);border-color:var(--yes-line)}
.badge.no{background:var(--no-bg);color:var(--no-ink);border-color:var(--no-line)}
.row .cert{font-size:11.5px;color:var(--ink-3);line-height:1.35}
.row .cert b{color:var(--ink-2);font-weight:500}
.warn{display:inline-block;font-size:11px;color:var(--unsure);border:1px solid var(--unsure);border-radius:4px;padding:0 5px;margin-top:3px}
.flags{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.flags button{padding:3px 8px;font-size:12px}
.flags button.on.w{background:var(--wrong);border-color:var(--wrong);color:#fff}
.flags button.on.u{background:var(--unsure);border-color:var(--unsure);color:#fff}
.flags button.on.o{background:var(--ok);border-color:var(--ok);color:#fff}
.flags input{width:100%;font-size:12px;padding:3px 6px;margin-top:2px}
.others{font-size:11px;color:var(--ink-3);width:100%}
.others .w{color:var(--wrong)} .others .u{color:var(--unsure)}
.hidden{display:none !important}

/* lightbox */
#lb:not([hidden]){position:fixed;inset:0;z-index:50;background:rgba(10,12,18,.82);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:20px}
#lb .frame{max-width:96vw;max-height:70vh;overflow:auto;background:#fff;border:1px solid var(--line-strong);box-shadow:var(--shadow)}
#lb img{display:block;image-rendering:pixelated}
#lb .info{background:var(--surface);color:var(--ink);border-radius:8px;padding:10px 14px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;max-width:96vw}
#lb .info .cert{color:var(--ink-3);font-size:12px}
#lb .info input{width:260px}
#lb .keys{color:#c9cfdd;font-size:12px}
</style>

<header class="top">
  <div><h1>Does the Text Fit? Audit</h1><span class="sub">set __SET__ · __N__ items · 12 cells × 6 levels × 15 seeds · crops at 1:1 pixels</span></div>
  <label>Rater <input type="text" id="rater" size="10" placeholder="your name"></label>
  <label><input type="checkbox" id="showAll"> show all raters</label>
  <label><input type="checkbox" id="onlyFlag"> only flagged</label>
  <button id="export">Export JSON</button>
  <span class="status" id="status">enter a rater name to start</span>
</header>

<div class="wrap">
<nav class="rail" id="rail"></nav>
<main>
  <section class="intro">
    <h2>What to flag</h2>
    <p>Each badge is the certificate's answer to the benchmark question, <em>Does any of the box's content extend beyond or fall outside the box?</em> Your job is to catch items where the picture does not support that answer.</p>
    <p><b>Wrong</b>: a <span class="badge yes">yes</span> with nothing visibly crossing the edge even at 3× zoom, or a <span class="badge no">no</span> with something crossing. Also wrong: broken rendering (garbled glyphs, misplaced Thai marks, a label touching the border). <b>Unsure</b>: you cannot decide either way. Anything you leave alone counts as OK once you press <em>Mark reviewed</em> on that table.</p>
    <p>Decoy items (cell 6) are <em>no</em> by definition: the outside word is a separate label, not the box's content. Flag them only for rendering faults. Items marked <span class="warn">auto: weak</span> have fewer than 6 overflow pixels, so look at those first.</p>
    <div class="keys">Zoom view keys: <span><kbd>←</kbd> <kbd>→</kbd> move</span> <span><kbd>W</kbd> wrong</span> <span><kbd>U</kbd> unsure</span> <span><kbd>O</kbd> clear</span> <span><kbd>N</kbd> note</span> <span><kbd>+</kbd> <kbd>−</kbd> zoom</span> <span><kbd>Esc</kbd> close</span></div>
  </section>
  <section class="attention" id="attention"></section>
  <div id="tables"></div>
</main>
</div>

<div id="lb" hidden>
  <div class="frame"><img id="lbimg" alt=""></div>
  <div class="info">
    <span class="mono" id="lbid"></span>
    <span id="lbbadge"></span>
    <span class="cert" id="lbcert"></span>
    <span class="flags" id="lbflags"></span>
    <input type="text" id="lbnote" placeholder="note (optional)">
    <span class="mono" id="lbzoom"></span>
  </div>
  <div class="keys">← → move · W wrong · U unsure · O clear · N note · + − zoom · Esc close</div>
</div>

<script>
const ITEMS = __ITEMS__;
const CELLS = __CELLS__;
const LEVEL_NAMES = __LEVEL_NAMES__;
const SET = "__SET__";
const byId = Object.fromEntries(ITEMS.map(it => [it.id, it]));
const groups = {};          // key cell|level -> [items]
for (const it of ITEMS) (groups[it.cell + "|" + it.level] ||= []).push(it);
for (const k in groups) groups[k].sort((a, b) => a.sid < b.sid ? -1 : 1);
const expected = (cell, level) => cell === "c06_decoy" || ["anchor", "m10", "m3", "m1"].includes(level) ? "no" : "yes";

// ---------- state
let rater = "";
let flags = {};             // id -> {status, note}
let done = {};              // cell|level -> true
let others = {};            // id -> [{rater,status}]
let db = null, unsubMine = [], unsubAll = null;
const lsKey = () => "audit:" + SET + ":" + rater;
const sanitize = s => s.trim().replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 40);

function saveLocal(){ try { localStorage.setItem(lsKey(), JSON.stringify({flags, done})); } catch (e) {} }
function loadLocal(){ try { const s = localStorage.getItem(lsKey()); if (s) { const o = JSON.parse(s); flags = o.flags || {}; done = o.done || {}; } } catch (e) {} }

async function setFlag(id, status, note){
  const it = byId[id];
  if (status === "ok" || status === "" || status == null) delete flags[id]; else flags[id] = {status, note: note || ""};
  saveLocal(); renderRow(id); updateRail();
  if (db && rater) {
    const ref = db.collection("flags").doc(rater + "~" + id);
    try {
      if (flags[id]) await ref.set({rater, item: id, cell: it.cell, level: it.level, status, note: note || "", ts: Date.now()});
      else await ref.delete();
    } catch (e) { setStatus("shared save failed (" + (e.code || "error") + "); kept in this browser", false); }
  }
}
async function setDone(key, val){
  if (val) done[key] = true; else delete done[key];
  saveLocal(); renderTableHead(key); updateRail();
  if (db && rater) {
    const [cell, level] = key.split("|");
    const ref = db.collection("progress").doc(rater + "~" + cell + "~" + level);
    try { if (val) await ref.set({rater, cell, level, done: true, ts: Date.now()}); else await ref.delete(); }
    catch (e) { setStatus("shared save failed (" + (e.code || "error") + "); kept in this browser", false); }
  }
}
function setStatus(msg, live){ const s = document.getElementById("status"); s.textContent = msg; s.classList.toggle("live", !!live); }

// ---------- shared store
async function connect(){
  try {
    const useCap = (window.claude && window.claude.use) ? window.claude.use("db") : Promise.resolve(null);
    db = await useCap;
  } catch (e) { db = null; }
  if (rater) startRater();
}
function startRater(){
  loadLocal();
  renderAll();
  for (const u of unsubMine) u(); unsubMine = [];
  if (!db) { setStatus("saving in this browser as " + rater + " — press Export JSON when done and send the file", false); document.getElementById("showAll").parentElement.hidden = true; return; }
  setStatus("connected to the shared store as " + rater, true);
  try {
    unsubMine.push(db.collection("flags").where("rater", "==", rater).limit(1000).onSnapshot(snap => {
      const remote = {};
      for (const d of snap.docs) { const x = d.data(); if (x && x.item) remote[x.item] = {status: x.status, note: x.note || ""}; }
      if (snap.metadata.fromCache && snap.empty) return;   // wait for a definitive answer before trusting an empty set
      flags = remote; saveLocal(); renderAll();
    }, e => setStatus("shared store error (" + e.code + "); browser copy still works", false)));
    unsubMine.push(db.collection("progress").where("rater", "==", rater).limit(1000).onSnapshot(snap => {
      const remote = {};
      for (const d of snap.docs) { const x = d.data(); if (x && x.cell) remote[x.cell + "|" + x.level] = true; }
      if (snap.metadata.fromCache && snap.empty) return;
      done = remote; saveLocal(); for (const k in groups) renderTableHead(k); updateRail();
    }, e => {}));
  } catch (e) { setStatus("shared store unavailable; saving in this browser only", false); }
}
function watchAll(on){
  if (unsubAll) { unsubAll(); unsubAll = null; }
  others = {};
  if (on && db) {
    unsubAll = db.collection("flags").limit(1000).onSnapshot(snap => {
      others = {};
      for (const d of snap.docs) { const x = d.data(); if (x && x.item && x.rater !== rater) (others[x.item] ||= []).push({rater: x.rater, status: x.status, note: x.note || ""}); }
      renderAll();
    }, e => {});
  } else renderAll();
}

// ---------- rendering
function rowHtml(it){
  const f = flags[it.id];
  const cls = f ? " f-" + f.status : "";
  let cert = `<b>${it.ov}</b> px outside · pen <b>${it.pen}</b> · clr <b>${it.clr}</b><br>eye <b>${it.eye7}</b>/${it.eye5}`;
  if (it.hclr != null) cert += ` · curve clr <b>${it.hclr}</b>`;
  if (it.gap != null) cert += ` · gap <b>${it.gap}</b>`;
  const warn = it.sub ? `<br><span class="warn">auto: sub-resolution</span>` : (it.weak ? `<br><span class="warn">auto: weak</span>` : "");
  const fam = it.family ? `<small>${it.family}</small>` : "";
  const oth = (others[it.id] || []).map(o => `<span class="${o.status === "wrong" ? "w" : "u"}">${o.rater}: ${o.status}${o.note ? " — " + o.note : ""}</span>`).join(" · ");
  return `<div class="row${cls}" data-id="${it.id}">
    <div class="sid">${it.sid}${fam}<small>${it.font} ${it.fs}px</small></div>
    <div class="cropwrap"><img class="crop" src="${it.src}" width="${it.w}" height="${it.h}" alt="" tabindex="0" data-id="${it.id}"></div>
    <div><span class="badge ${it.label}">${it.label}</span></div>
    <div class="cert">${cert}${warn}</div>
    <div class="flags">
      <button class="o${f ? "" : " on"}" data-s="ok">OK</button>
      <button class="w${f && f.status === "wrong" ? " on" : ""}" data-s="wrong">Wrong</button>
      <button class="u${f && f.status === "unsure" ? " on" : ""}" data-s="unsure">Unsure</button>
      ${f ? `<input type="text" placeholder="note" value="${(f.note || "").replace(/"/g, "&quot;")}" data-note="${it.id}">` : ""}
      ${oth ? `<div class="others">${oth}</div>` : ""}
    </div></div>`;
}
function renderRow(id){
  const el = document.querySelector(`.row[data-id="${id}"]`);
  if (!el) return;
  const tmp = document.createElement("div"); tmp.innerHTML = rowHtml(byId[id]);
  el.replaceWith(tmp.firstElementChild);
  applyFilter();
}
function renderTableHead(key){
  const [cell, level] = key.split("|");
  const h = document.getElementById("h-" + cell + "-" + level);
  if (!h) return;
  const n = groups[key].length, nf = groups[key].filter(it => flags[it.id]).length;
  h.querySelector(".cnt").textContent = `${n} items · ${nf} flagged`;
  const b = h.querySelector("button");
  b.textContent = done[key] ? "Reviewed ✓" : "Mark reviewed";
  b.classList.toggle("done", !!done[key]);
}
function renderAll(){
  const root = document.getElementById("tables");
  let html = "";
  for (const c of CELLS) {
    html += `<div class="cellhead" id="cell-${c.cell}"><span class="num">${c.num}</span><h2>${c.title}</h2><span class="blurb">${c.blurb}</span></div>`;
    for (const lv of c.levels) {
      const key = c.cell + "|" + lv, items = groups[key] || [];
      const exp = expected(c.cell, lv);
      html += `<section class="tbl" id="t-${c.cell}-${lv}"><header id="h-${c.cell}-${lv}"><h3>${LEVEL_NAMES[lv] || lv}</h3><span class="exp">expected <span class="badge ${exp}">${exp}</span></span><span class="cnt"></span><button data-key="${key}">Mark reviewed</button></header><div class="rows">`;
      html += items.map(rowHtml).join("");
      html += `</div></section>`;
    }
  }
  root.innerHTML = html;
  for (const k in groups) renderTableHead(k);
  renderAttention(); updateRail(); applyFilter();
}
function renderAttention(){
  const list = ITEMS.filter(it => it.sub || it.weak);
  const el = document.getElementById("attention");
  el.innerHTML = `<h3>Look at these first · ${list.length} items with fewer than 6 overflow pixels</h3><ul>` +
    list.map(it => `<li><a href="#t-${it.cell}-${it.level}" data-open="${it.id}">${it.id}</a> — ${it.ov} px outside, ${it.eye7} survive at 768 wide${it.sub ? " (flagged sub-resolution)" : ""}</li>`).join("") + `</ul>`;
}
function updateRail(){
  const rail = document.getElementById("rail");
  const totalFlags = Object.keys(flags).length, totalDone = Object.keys(done).length;
  let html = `<div class="tot">${totalDone} / ${Object.keys(groups).length} tables reviewed · ${totalFlags} flagged</div>`;
  for (const c of CELLS) {
    html += `<div class="cell"><a href="#cell-${c.cell}">${c.num} · ${c.title}</a><div class="chips">`;
    for (const lv of c.levels) {
      const key = c.cell + "|" + lv, nf = (groups[key] || []).filter(it => flags[it.id]).length;
      html += `<a class="chip${done[key] ? " done" : ""}" href="#t-${c.cell}-${lv}">${done[key] ? "✓ " : ""}${shortLevel(lv)}${nf ? `<span class="n">${nf}</span>` : ""}</a>`;
    }
    html += `</div></div>`;
  }
  rail.innerHTML = html;
}
function shortLevel(lv){ return lv.replace("incomplete_", "inc·").replace("complete_", "cmp·").replace("gTwin", "g4").replace("anchor", "anc").replace("corner", "crn"); }
function applyFilter(){
  const only = document.getElementById("onlyFlag").checked;
  for (const el of document.querySelectorAll(".row")) el.classList.toggle("hidden", only && !flags[el.dataset.id]);
}

// ---------- lightbox
let lbId = null, zoom = 3;
function openLb(id){
  lbId = id; const it = byId[id];
  const lb = document.getElementById("lb"); lb.hidden = false;
  const img = document.getElementById("lbimg"); img.src = it.src; img.width = it.w * zoom; img.height = it.h * zoom;
  document.getElementById("lbid").textContent = it.id + (it.family ? " · " + it.family : "");
  document.getElementById("lbbadge").innerHTML = `<span class="badge ${it.label}">${it.label}</span>`;
  document.getElementById("lbcert").textContent = `${it.ov} px outside · penetration ${it.pen} · clearance ${it.clr} · eye ${it.eye7}/${it.eye5}` + (it.hclr != null ? ` · curve clearance ${it.hclr}` : "") + (it.gap != null ? ` · gap ${it.gap}` : "");
  document.getElementById("lbzoom").textContent = zoom + "×";
  const f = flags[id];
  document.getElementById("lbflags").innerHTML = `<button class="o${f ? "" : " on"}" data-s="ok">OK</button><button class="w${f && f.status === "wrong" ? " on" : ""}" data-s="wrong">Wrong</button><button class="u${f && f.status === "unsure" ? " on" : ""}" data-s="unsure">Unsure</button>`;
  document.getElementById("lbnote").value = f ? (f.note || "") : "";
}
function closeLb(){ document.getElementById("lb").hidden = true; lbId = null; }
function lbMove(d){
  const it = byId[lbId], g = groups[it.cell + "|" + it.level];
  const i = g.findIndex(x => x.id === lbId), j = i + d;
  if (j >= 0 && j < g.length) openLb(g[j].id);
}

// ---------- events
document.addEventListener("click", e => {
  const t = e.target;
  if (t.classList.contains("crop")) { openLb(t.dataset.id); return; }
  if (t.dataset.open) { e.preventDefault(); openLb(t.dataset.open); return; }
  if (t.dataset.key) { setDone(t.dataset.key, !done[t.dataset.key]); return; }
  if (t.dataset.s) {
    const row = t.closest(".row");
    const id = row ? row.dataset.id : lbId;
    if (!id) return;
    if (!rater) { alert("Enter a rater name first."); return; }
    const note = row ? (row.querySelector("input[data-note]") || {}).value : document.getElementById("lbnote").value;
    setFlag(id, t.dataset.s, note);
    if (lbId === id) openLb(id);
    return;
  }
  if (t.id === "lb") closeLb();
});
document.addEventListener("change", e => {
  const t = e.target;
  if (t.dataset.note) { const f = flags[t.dataset.note]; if (f) setFlag(t.dataset.note, f.status, t.value); }
  if (t.id === "lbnote" && lbId) { const f = flags[lbId]; if (f) setFlag(lbId, f.status, t.value); }
  if (t.id === "onlyFlag") applyFilter();
  if (t.id === "showAll") watchAll(t.checked);
  if (t.id === "rater") { rater = sanitize(t.value); try { localStorage.setItem("audit:rater", rater); } catch (x) {} if (rater) startRater(); }
});
document.addEventListener("keydown", e => {
  if (lbId == null) return;
  if (e.target.id === "lbnote") { if (e.key === "Escape") { e.target.blur(); } return; }
  const k = e.key.toLowerCase();
  if (e.key === "Escape") closeLb();
  else if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); lbMove(1); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); lbMove(-1); }
  else if (k === "w" || k === "u" || k === "o") {
    if (!rater) { alert("Enter a rater name first."); return; }
    setFlag(lbId, k === "w" ? "wrong" : k === "u" ? "unsure" : "ok", document.getElementById("lbnote").value);
    lbMove(1); if (lbId) openLb(lbId);
  }
  else if (k === "n") { e.preventDefault(); document.getElementById("lbnote").focus(); }
  else if (e.key === "+" || e.key === "=") { zoom = Math.min(6, zoom + 1); openLb(lbId); }
  else if (e.key === "-") { zoom = Math.max(1, zoom - 1); openLb(lbId); }
});
document.getElementById("export").onclick = async () => {
  const out = {set: SET, rater, exported: new Date().toISOString(), flags, reviewed: Object.keys(done)};
  const text = JSON.stringify(out, null, 1), filename = `audit_${SET}_${rater || "anon"}.json`;
  let dl = null;
  try { dl = (window.claude && window.claude.use) ? await window.claude.use("downloads") : null; } catch (e) { dl = null; }
  if (dl) {
    try { await dl.save({filename, data: text}); setStatus("exported " + filename, true); }
    catch (e) { if (e && e.code !== "declined") setStatus("export failed (" + (e.code || "error") + ")", false); }
    return;
  }
  const blob = new Blob([text], {type: "application/json"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
};

// ---------- boot
try { rater = localStorage.getItem("audit:rater") || ""; } catch (e) {}
document.getElementById("rater").value = rater;
renderAll();
connect();
</script>
"""


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v1", sys.argv[2] if len(sys.argv) > 2 else None)
