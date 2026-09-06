"""QC over a build: summary tables (markdown) + per-cell contact sheets.

Usage: python qc.py v1
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render import GEN, H, W

LEVEL_ORDER = {
    "default": ["anchor", "m10", "m3", "p4", "p12", "p30"],
    "c05_wordgap": ["anchor", "m10", "m3", "short", "medium", "long"],
    "c06_decoy": ["incomplete_gTwin", "incomplete_g12", "incomplete_g30", "complete_gTwin", "complete_g12", "complete_g30"],
    "c07_pill": ["anchor", "m10", "m3", "corner", "p4", "p12"],
    "c11_marks": ["anchor", "m3", "m1", "p3", "p6", "p9"],
}


def load(name):
    return [json.loads(l) for l in (GEN / "out" / name / "manifest.jsonl").open(encoding="utf-8")]


def summary(recs, path: Path):
    cells = sorted({r["cell"] for r in recs})
    lines = ["# QC summary", "", f"records: {len(recs)}", ""]
    tot_yes = sum(r["label"] == "yes" for r in recs)
    lines += [f"positives: {tot_yes} ({100 * tot_yes / len(recs):.1f} %), negatives: {len(recs) - tot_yes}", ""]
    lines += ["| cell | level | n | yes | overflow px (med) | penetration (med) | clearance (med) | eye768 (min/med) | eye512 (min/med) | sub_res |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for cell in cells:
        order = LEVEL_ORDER.get(cell, LEVEL_ORDER["default"])
        rs = [r for r in recs if r["cell"] == cell]
        for lv in order:
            g = [r for r in rs if r["level"] == lv]
            if not g:
                continue
            ov = [r["cert"]["overflow_px"] for r in g]
            pen = [r["cert"]["penetration"] for r in g]
            clr = [r["cert"]["clearance"] for r in g]
            e7 = [r["eye768"] for r in g]; e5 = [r["eye512"] for r in g]
            lines.append(f"| {cell} | {lv} | {len(g)} | {sum(r['label'] == 'yes' for r in g)} | {statistics.median(ov):.0f} | "
                         f"{statistics.median(pen):.1f} | {statistics.median(clr):.1f} | {min(e7)}/{statistics.median(e7):.0f} | "
                         f"{min(e5)}/{statistics.median(e5):.0f} | {sum(r['sub_resolution'] for r in g)} |")
    lines += ["", "## Flags", ""]
    flagged = [r for r in recs if r["sub_resolution"]]
    lines.append(f"sub_resolution (yes items with < 2 surviving px at 768): {len(flagged)}")
    for r in flagged:
        lines.append(f"- {r['cell']} {r['level']} {r['sid']}: overflow {r['cert']['overflow_px']} px, eye {r['eye768']}/{r['eye512']}")
    weak = [r for r in recs if r["label"] == "yes" and r["cert"]["overflow_px"] < 6 and not r["sub_resolution"]]
    lines.append(f"\nweak positives (< 6 overflow px, not flagged): {len(weak)}")
    for r in weak:
        lines.append(f"- {r['cell']} {r['level']} {r['sid']}: overflow {r['cert']['overflow_px']} px, eye {r['eye768']}/{r['eye512']}")
    # anchor margins (directional) and level/label consistency
    capped, mism = [], []
    for r in recs:
        bx, by, bw, bh = r["geo"]; il, it, ir, ib = r["ink_bbox"]
        if r["level"] == "anchor":
            if r["cell"] in ("c09_bottom", "c12_thaiwrap") or (r["cell"] == "c11_marks" and "below" in r["note"]):
                m = (by + bh - 1 - ib) / bh
            elif r["cell"] == "c11_marks":
                m = (it - by) / bh
            else:
                m = (bx + bw - 1 - ir) / bw
            if m < 0.3:
                capped.append(f"{r['cell']} {r['sid']} margin={m:.2f}")
        expect = "no" if (r["cell"] == "c06_decoy" or r["level"] in ("anchor", "m10", "m3", "m1")) else "yes"
        if r["label"] != expect:
            mism.append(f"{r['cell']} {r['level']} {r['sid']} label={r['label']} overflow={r['cert']['overflow_px']}")
    lines.append(f"\nanchor items with directional margin below 30 % of the box: {len(capped)}")
    lines += [f"- {c}" for c in capped]
    lines.append(f"\nlevel/label mismatches (certificate disagrees with the level's intended label): {len(mism)}")
    lines += [f"- {m}" for m in mism]
    # cell 11 mark heights, cell 3 ink ratio, cell 9/12 line counts
    for key in ("mark_height", "mark_depth", "blob_ink", "lines"):
        vals = []
        for r in recs:
            for part in r["note"].split(";"):
                if part.startswith(key + "="):
                    vals.append(int(part.split("=")[1]))
        if vals:
            lines.append(f"\n{key}: min {min(vals)}, median {statistics.median(vals):.0f}, max {max(vals)} (over {len(vals)} items)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path)


def sheets(recs, out: Path, scale=0.7):
    font = ImageFont.truetype(str(GEN / "fonts" / "Inter.ttf"), 12)
    cells = sorted({r["cell"] for r in recs})
    for cell in cells:
        order = LEVEL_ORDER.get(cell, LEVEL_ORDER["default"])
        rs = [r for r in recs if r["cell"] == cell]
        sids = sorted({r["sid"] for r in rs})
        crops = {}
        for r in rs:
            bx, by, bw, bh = r["geo"]; il, it, ir, ib = r["ink_bbox"]
            x0, y0 = max(min(bx, il) - 16, 0), max(min(by, it) - 12, 0)
            x1, y1 = min(max(bx + bw, ir + 1) + 16, W), min(max(by + bh, ib + 1) + 12, H)
            im = Image.open(r["path"]).crop((x0, y0, x1, y1))
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
            crops[(r["sid"], r["level"])] = (im, f"{r['level']} {r['label']} ov={r['cert']['overflow_px']} eye={r['eye768']}")
        tw = max(im.width for im, _ in crops.values()) + 10
        th = max(im.height for im, _ in crops.values()) + 18
        sheet = Image.new("RGB", (len(order) * tw + 10, len(sids) * th + 30), "#e8e8e8")
        d = ImageDraw.Draw(sheet)
        d.text((8, 6), f"{cell}  ({len(rs)} images)", fill="#111", font=font)
        for j, sid in enumerate(sids):
            for k, lv in enumerate(order):
                if (sid, lv) not in crops:
                    continue
                im, cap = crops[(sid, lv)]
                x, y = 8 + k * tw, 30 + j * th
                d.text((x, y), f"{sid} {cap}", fill="#333", font=font)
                sheet.paste(im, (x, y + 14))
        sheet.save(out / f"sheet_{cell}.png")
    print("sheets written to", out)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "v1"
    recs = load(name)
    out = GEN / "out" / name
    summary(recs, out / "qc_summary.md")
    sheets(recs, out)
