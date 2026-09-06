"""Write a single-file human grading page next to a build's images.

Usage: python make_grader.py v1   -> gen/out/v1/grader.html
Modes: validity (zoom allowed, unlimited time)  |  baseline (no zoom, one pass, timed)
Answers are kept in localStorage per rater and exported as JSONL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from render import GEN

PROMPT_MAIN = "Does any of the box's content extend beyond or fall outside the box?"


def main(name: str):
    out = GEN / "out" / name
    recs = [json.loads(l) for l in (out / "manifest.jsonl").open(encoding="utf-8")]
    items = [{"id": Path(r["path"]).stem, "src": Path(r["path"]).name, "cell": r["cell"], "level": r["level"]} for r in recs]
    page = TEMPLATE.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)).replace("__PROMPT__", PROMPT_MAIN)
    (out / "grader.html").write_text(page, encoding="utf-8")
    print(out / "grader.html", len(items), "items")


TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Overflow grader</title>
<style>
body{margin:0;font:15px system-ui,sans-serif;background:#f4f4f4;color:#111}
#top{padding:10px 16px;background:#fff;border-bottom:1px solid #ddd;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
#stage{display:flex;justify-content:center;padding:16px}
#img{border:1px solid #ccc;background:#fff;image-rendering:auto;max-width:100%}
#q{font-size:18px;text-align:center;padding:8px}
#keys{text-align:center;color:#555}
button{font:inherit;padding:6px 12px}
.zoomed #img{max-width:none;width:2048px}
#zoomwrap{overflow:auto;max-width:100vw}
input,select{font:inherit;padding:4px}
</style></head><body>
<div id="top">
  <label>Rater <input id="rater" size="10"></label>
  <label>Mode <select id="mode"><option value="validity">validity (zoom ok, no time limit)</option><option value="baseline">baseline (no zoom, one pass)</option></select></label>
  <button id="start">Start / resume</button>
  <span id="prog"></span>
  <button id="zoom" style="display:none">Zoom (z)</button>
  <button id="export">Export JSONL</button>
</div>
<div id="q">__PROMPT__</div>
<div id="keys"><b>Y</b> = yes &nbsp; <b>N</b> = no &nbsp; <b>U</b> = unsure / undecidable &nbsp; <b>←</b> = back</div>
<div id="stage"><div id="zoomwrap"><img id="img"></div></div>
<script>
const ITEMS = __ITEMS__;
let order = [], i = 0, key = null, answers = {}, t0 = 0, mode = 'validity';
function seedShuffle(arr, seed){ // deterministic per rater
  let s = 0; for (const ch of seed) s = (s * 31 + ch.charCodeAt(0)) >>> 0;
  const a = arr.slice(); for (let k = a.length - 1; k > 0; k--) { s = (s * 1664525 + 1013904223) >>> 0; const j = s % (k + 1); [a[k], a[j]] = [a[j], a[k]]; } return a;
}
function save(){ localStorage.setItem(key, JSON.stringify({i, answers})); }
function show(){
  if (i >= order.length) { document.getElementById('img').src = ''; document.getElementById('prog').textContent = 'done (' + order.length + ')'; return; }
  const it = order[i]; document.getElementById('img').src = it.src; t0 = performance.now();
  document.getElementById('prog').textContent = (i + 1) + ' / ' + order.length;
  document.body.classList.remove('zoomed');
}
document.getElementById('start').onclick = () => {
  const r = document.getElementById('rater').value.trim(); if (!r) { alert('enter rater id'); return; }
  mode = document.getElementById('mode').value; key = 'grader:' + mode + ':' + r;
  order = seedShuffle(ITEMS, r + mode);
  const saved = localStorage.getItem(key); if (saved) { const s = JSON.parse(saved); i = s.i; answers = s.answers; }
  document.getElementById('zoom').style.display = mode === 'validity' ? '' : 'none';
  show();
};
document.getElementById('zoom').onclick = () => document.body.classList.toggle('zoomed');
function answer(a){
  if (!key || i >= order.length) return;
  const it = order[i];
  answers[it.id] = {answer: a, ms: Math.round(performance.now() - t0), mode, zoomed: document.body.classList.contains('zoomed'), cell: it.cell, level: it.level, ts: Date.now()};
  i++; save(); show();
}
document.addEventListener('keydown', e => {
  const k = e.key.toLowerCase();
  if (k === 'y') answer('yes'); else if (k === 'n') answer('no'); else if (k === 'u') answer('unsure');
  else if (k === 'z' && mode === 'validity') document.body.classList.toggle('zoomed');
  else if (e.key === 'ArrowLeft' && i > 0) { i--; save(); show(); }
});
document.getElementById('export').onclick = () => {
  const lines = Object.entries(answers).map(([id, a]) => JSON.stringify({id, rater: document.getElementById('rater').value.trim(), ...a}));
  const blob = new Blob([lines.join('\n') + '\n'], {type: 'application/jsonl'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'answers_' + mode + '_' + document.getElementById('rater').value.trim() + '.jsonl'; a.click();
};
</script></body></html>"""


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v1")
