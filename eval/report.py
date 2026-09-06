"""Quick summary of a run's responses.jsonl.

    python eval/report.py pilot                    # per slot x setting: acc, hit, FA, flips, tokens, latency, errors
    python eval/report.py pilot --items            # plus per-item answer grid (majority over repeats)
    python eval/report.py core --prompt para1      # one prompt at a time (default: main)

Answers are re-parsed from the stored text with the current parser. The pooled
line excludes cell 11 (reported separately by protocol); per-cell rows are
unaffected. Repeat consistency is computed within one (slot, setting, prompt).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse import parse_yes_no  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POOL_EXCLUDE = {"c11_marks"}


def load(run):
    rows = {}
    for line in (ROOT / "eval" / "out" / run / "responses.jsonl").open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows[r["key"]] = r  # latest row per key wins (retries append)
    out = list(rows.values())
    for r in out:
        r["answer"] = "error" if r.get("error") else parse_yes_no(r.get("text", ""))
    return out


def summarize(rows):
    rows = [r for r in rows if r["cell"] not in POOL_EXCLUDE]
    groups = defaultdict(list)
    for r in rows:
        groups[(r["slot"], r["setting"])].append(r)
    print(f"pooled over cells except {sorted(POOL_EXCLUDE)}")
    print(f"{'slot':11} {'set':4} {'n':>4} {'err':>3} {'unp':>3} {'acc':>5} {'hit':>5} {'FA':>5} {'flip':>5} {'reas':>6} {'out':>5} {'lat':>5}")
    for (slot, setting), rs in sorted(groups.items()):
        ok = [r for r in rs if not r["error"]]
        err = len(rs) - len(ok)
        unp = sum(r["answer"] == "unparsed" for r in ok)
        scored = [r for r in ok if r["answer"] in ("yes", "no")]
        acc = sum(r["answer"] == r["label"] for r in scored) / max(1, len(scored))
        pos = [r for r in scored if r["label"] == "yes"]
        neg = [r for r in scored if r["label"] == "no"]
        hit = sum(r["answer"] == "yes" for r in pos) / max(1, len(pos))
        fa = sum(r["answer"] == "yes" for r in neg) / max(1, len(neg))
        # self-consistency: items with >1 repeat where answers disagree
        by_item = defaultdict(list)
        for r in scored:
            by_item[r["item"]].append(r["answer"])
        multi = [v for v in by_item.values() if len(v) > 1]
        flip = sum(len(set(v)) > 1 for v in multi) / max(1, len(multi)) if multi else float("nan")
        reas = [r["usage"].get("reasoning") or 0 for r in ok]
        outt = [r["usage"].get("out") or 0 for r in ok]
        lat = [r["latency"] for r in ok]
        mean = lambda xs: sum(xs) / max(1, len(xs))  # noqa: E731
        print(f"{slot:11} {setting:4} {len(rs):4d} {err:3d} {unp:3d} {acc:5.2f} {hit:5.2f} {fa:5.2f} {flip:5.2f} {mean(reas):6.0f} {mean(outt):5.0f} {mean(lat):5.1f}")
    errs = Counter((r["slot"], r["error"][:90]) for r in rows if r["error"])
    if errs:
        print("\nerrors:")
        for (slot, e), n in errs.most_common(10):
            print(f"  {n:3d} {slot:11} {e}")


def item_grid(rows):
    slots = sorted({(r["slot"], r["setting"]) for r in rows})
    items = sorted({(r["cell"], r["level"], r["item"], r["label"]) for r in rows})
    by = defaultdict(list)
    for r in rows:
        if r["answer"] in ("yes", "no"):
            by[(r["item"], r["slot"], r["setting"])].append(r["answer"])
    head = " ".join(f"{s[0][:6]}/{s[1]:<3}" for s in slots)
    print(f"\n{'item':34} lab  {head}")
    for cell, level, item, label in items:
        cells = []
        for s in slots:
            v = by.get((item, s[0], s[1]), [])
            if not v:
                cells.append("   -      ")
                continue
            ny = sum(a == "yes" for a in v)
            maj = "yes" if ny * 2 > len(v) else ("no" if ny * 2 < len(v) else "tie")
            mark = "." if maj == label else "X"
            cells.append(f"{maj:>3}{ny}/{len(v)}{mark}    ")
        print(f"{item:34} {label:3}  {' '.join(cells)}")


if __name__ == "__main__":
    run = sys.argv[1]
    prompt = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else "main"
    rows = [r for r in load(run) if r.get("prompt", "main") == prompt]
    print(f"run={run} prompt={prompt} rows={len(rows)}")
    summarize(rows)
    if "--items" in sys.argv:
        item_grid(rows)
