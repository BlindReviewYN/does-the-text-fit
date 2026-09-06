"""Full stimulus build: 12 cells x 6 levels x 15 seeds = 1,080 images + manifest.

Usage:  python build.py [out_name] [--cells c01,c05] [--rows 0,1,2]
"""
from __future__ import annotations

import argparse
import html as _html
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

from render import (BORDER, GEN, H, LEVELS_RIGHT, MARGIN, MARKER, PAD, W, Content, Renderer, Seed, Stim,
                    bar_from_text, certify, finalize, geom_bottom, geom_right, geom_top, gibberish, make_mask,
                    page_html, pill_h_clearance, render_content, render_text, skyline_from_text, strip_marks,
                    text_css, word_extents)

POOLS = json.loads((GEN / "seeds" / "pools.json").read_text(encoding="utf-8"))
EN_FONTS = ["Inter", "Roboto", "SourceSans3", "OpenSans"]
TH_FONTS = ["Sarabun", "NotoSansThai", "Prompt"]
NEG3 = [("anchor", "anchor"), ("m10", -10), ("m3", -3)]


# ----------------------------------------------------------------------------- styling & layout

def style(i: int, lang: str, sizes: list[int], lh: float) -> dict:
    pal = POOLS["palettes"][(i * 2 + i // 5) % 5]
    fonts = EN_FONTS if lang == "en" else TH_FONTS
    return dict(font=fonts[i % len(fonts)], fs=sizes[(i // 3) % len(sizes)] if lang == "th" and len(sizes) == 3
                else sizes[i % len(sizes)], lh=lh, **pal)


def measure_box(R: Renderer, seed: Seed, string: str, width=None, word_spacing=0) -> tuple[float, float]:
    css = text_css(seed, width, word_spacing)
    m = R.measure_only(page_html(seed.font, seed.lang, css, _html.escape(string) + MARKER))
    l, t, r, b = m["cbox"]
    return r - l, b - t


def place(rng: random.Random, w: float, h: float, need_right: float = 0, need_bottom: float = 0, need_top: float = 0,
          pad: int = PAD + BORDER) -> tuple[int, int]:
    """Choose the content's top-left so every level of the box stays >= MARGIN from the canvas edge.
    need_*: extra canvas needed beyond the content box in that direction (anchor margins, outside runs)."""
    x_lo, x_hi = MARGIN + pad, W - MARGIN - pad - int(math.ceil(w)) - int(math.ceil(need_right))
    y_lo, y_hi = MARGIN + pad + int(math.ceil(need_top)), H - MARGIN - pad - int(math.ceil(h)) - int(math.ceil(need_bottom))
    x = rng.randint(x_lo, max(x_lo, x_hi))
    y = rng.randint(y_lo, max(y_lo, y_hi))
    return x, y


def anchor_extra(w: float, pad: int = PAD + BORDER) -> float:
    """Extra width the anchor level needs beyond the content box (40 % margin of the box)."""
    return (w + 2 * pad) / 0.6 - (w + 2 * pad)


# ----------------------------------------------------------------------------- cells

def cell_right(R, seed, string, out, cell, boundary="border", note=""):
    c = render_text(R, seed, string)
    return [finalize(R, seed, c, "rect", boundary, geom_right(c, p), out, seed.sid, cell, n, p, note=note)
            for n, p in LEVELS_RIGHT], c


def cell_bar(R, seed, c_text, out, cell="c02_bar"):
    body, _ = bar_from_text(c_text, seed)
    c = render_content(R, seed, "bar", "left:0;top:0;", body)
    c.cbox, c.baseline = c_text.cbox, c_text.baseline
    note = f"text_ink={int(c_text.ink.sum())};bar_ink={int(c.ink.sum())}"
    return [finalize(R, seed, c, "rect", "border", geom_right(c, p), out, seed.sid, cell, n, p, note=note)
            for n, p in LEVELS_RIGHT]


def cell_skyline(R, seed, c_text, out, cell="c03_matched"):
    body = skyline_from_text(c_text, seed.text)
    c = render_content(R, seed, "skyline", "left:0;top:0;", body)
    c.cbox, c.baseline = c_text.cbox, c_text.baseline
    note = f"text_ink={int(c_text.ink.sum())};blob_ink={int(c.ink.sum())}"
    return [finalize(R, seed, c, "rect", "border", geom_right(c, p), out, seed.sid, cell, n, p, note=note)
            for n, p in LEVELS_RIGHT]


def _gapped(R, seed, base, label_span=None, need=9, ws=None):
    if ws is None:
        c = render_text(R, seed, base, label_span=label_span)
        we = word_extents(c)
        ws = max(0, need - (we[-1][0] - we[-2][1] - 1))
    c = render_text(R, seed, base, word_spacing=ws, label_span=label_span)
    return c, word_extents(c), ws


def seed_word_spacing(R, seed, frame, fillers, label, need=9):
    ws = 0
    for f in list(fillers) + [label]:
        _, _, w = _gapped(R, seed, f"{frame} {f}", need=need)
        ws = max(ws, w)
    return ws


def cell_wordgap(R, seed, frame, fillers, ws, out, cell="c05_wordgap"):
    stims = []
    c_med = render_text(R, seed, f"{frame} {fillers[1]}", word_spacing=ws)
    for n, p in NEG3:
        stims.append(finalize(R, seed, c_med, "rect", "border", geom_right(c_med, p), out, seed.sid, cell, n, p,
                              note=f"word={fillers[1]};word_spacing={ws}"))
    for n, filler in zip(["short", "medium", "long"], fillers):
        c, we, _ = _gapped(R, seed, f"{frame} {filler}", ws=ws)
        pen_r, last_l = we[-2][1], we[-1][0]
        last_col = pen_r + 3 + BORDER
        bx, by, _, bh = geom_right(c, 0)
        geo = (bx, by, last_col - bx + 1, bh)
        stims.append(finalize(R, seed, c, "rect", "border", geo, out, seed.sid, cell, n, f"gap{last_l - last_col - 1}",
                              note=f"word={filler};word_spacing={ws}", extra_cert={"gap": last_l - last_col - 1}))
    return stims


def label_gap(ink, last_col: int) -> int:
    """Empty columns between the box's last column and the first ink to its right (the label's border)."""
    cols = np.nonzero(ink[:, last_col + 1:].any(axis=0))[0]
    return int(cols.min()) if len(cols) else -1


def cell_decoy(R, seed, frame, medium, label, ws, out, cell="c06_decoy"):
    """Decoy = the cell-5 twin with the outside word replaced by a bordered control (same font, size, colour).
    Levels: gap 4 (twin) / 12 / 30 px between the box border and the control's border x {incomplete, complete}."""
    style = f"border:{BORDER}px solid {seed.border};border-radius:4px;padding:1px 8px;"
    stims = []
    for comp in ["incomplete", "complete"]:
        base = frame if comp == "incomplete" else f"{frame} {medium}"
        c0 = render_text(R, seed, base, word_spacing=ws, label_span=(label, 0, style))
        we = word_extents(c0)
        last_col = we[-2][1] + 3 + BORDER
        bx, by, _, bh = geom_right(c0, 0)
        geo = (bx, by, last_col - bx + 1, bh)
        g0 = label_gap(c0.ink, last_col)
        for gname, g in [("gTwin", 4), ("g12", 12), ("g30", 30)]:
            c = render_text(R, seed, base, word_spacing=ws, label_span=(label, g - g0, style))
            mg = label_gap(c.ink, last_col)
            if mg != g:   # fractional inline positioning: correct once
                c = render_text(R, seed, base, word_spacing=ws, label_span=(label, g - g0 + (g - mg), style))
                mg = label_gap(c.ink, last_col)
            stims.append(finalize(R, seed, c, "rect", "border", geo, out, seed.sid, cell, f"{comp}_{gname}", g,
                                  label_rule="no", note=f"label={label};word_spacing={ws};{comp};button",
                                  extra_cert={"min_gap": mg}))
    return stims


def cell_pill(R, seed, string, out, cell="c07_pill", ratio=1.45):
    c = render_text(R, seed, string)
    l, t, r, b = c.cbox
    bh = int(round(ratio * seed.fs))
    by = int(round((t + b) / 2 - bh / 2))
    bx = int(math.floor(l)) - int(round(bh / 2))
    ir = c.bbox[2]
    bw0 = ir - bx + 1
    levels = []
    for n, target in [("m3", 3), ("m10", 10)]:
        bw = bw0
        while pill_h_clearance(c.ink, bx, by, bw, bh) < target and bw < bw0 + 120:
            bw += 1
        levels.append((n, f"clear{target}", bw))
    levels = [("anchor", "anchor", min(int(round(bw0 / 0.6)), W - MARGIN - bx))] + levels
    levels += [("corner", "corner", bw0), ("p4", 4, bw0 - 4), ("p12", 12, bw0 - 12)]
    return [finalize(R, seed, c, "pill", "fill", (bx, by, bw, bh), out, seed.sid, cell, n, p,
                     extra_cert={"h_clearance": pill_h_clearance(c.ink, bx, by, bw, bh)}, note=f"ratio={ratio}")
            for n, p, bw in levels]


def cell_bottom(R, seed, paragraph, out, cell, bw=320):
    tw = bw - 2 * (PAD + BORDER)
    c = render_text(R, seed, paragraph, width=tw)
    bx = int(math.floor(c.cbox[0])) - PAD - BORDER
    lines = int(round((c.cbox[3] - c.cbox[1]) / (seed.fs * seed.lh)))
    return [finalize(R, seed, c, "rect", "border", geom_bottom(c, p, bx, bw), out, seed.sid, cell, n, p,
                     note=f"lines={lines};box_w={bw}") for n, p in LEVELS_RIGHT]


def cell_thai_marks(R, seed, string, family, out, cell="c11_marks"):
    c = render_text(R, seed, string)
    cb = render_text(R, seed, strip_marks(string))
    bx, by, bw, bh = geom_right(c, "anchor")
    levels = [("anchor", "anchor"), ("m3", -3), ("m1", -1), ("p3", 3), ("p6", 6), ("p9", 9)]
    stims = []
    if family != "below":
        note = f"family={family};mark_height={cb.bbox[1] - c.bbox[1]}"
        for n, p in levels:
            stims.append(finalize(R, seed, c, "rect", "border", geom_top(c, p, bx, bw), out, seed.sid, cell, n, p, note=note))
    else:
        note = f"family={family};mark_depth={c.bbox[3] - cb.bbox[3]}"
        for n, p in levels:
            stims.append(finalize(R, seed, c, "rect", "border", geom_bottom(c, p, bx, bw), out, seed.sid, cell, n, p, note=note))
    return stims


# ----------------------------------------------------------------------------- orchestration

def build(out: Path, cells: set[str] | None, rows: list[int]):
    out.mkdir(parents=True, exist_ok=True)
    R = Renderer()
    records = []
    t0 = time.time()

    def add(stims, **meta):
        for s in stims:
            d = s.__dict__.copy(); d["geo"] = list(s.geo); d["ink_bbox"] = list(s.ink_bbox)
            d.update(meta)
            records.append(d)

    def want(cell):
        return cells is None or cell in cells

    try:
        # ---- P1: EN frames -> cells 1,2,3,4,5,6,8 (shared position per row)
        for i in rows:
            row = POOLS["P1_en_frames"][i]
            st = style(i, "en", [14, 16, 18, 20, 22], 1.6)
            seed = Seed(f"en{i:02d}", st["font"], "en", st["fs"], st["text"], st["border"], st["fill"], 0, 0, st["lh"])
            rng = random.Random(f"P1-{i}")
            w_long, h = measure_box(R, seed, f"{row['frame']} {row['long']}")
            w_run, _ = measure_box(R, seed, f"{row['frame']} {row['medium']} {row['label']}", word_spacing=4)
            need_right = max(anchor_extra(w_long), w_run - w_long + 30 + 24)
            seed.x, seed.y = place(rng, max(w_long, w_run), h, need_right=need_right)
            meta = dict(pool="P1", row=i, font=st["font"], fs=st["fs"], palette=(i * 2 + i // 5) % 5)
            long_s = f"{row['frame']} {row['long']}"
            c1 = None
            if want("c01_base") or want("c02_bar") or want("c03_matched"):
                s1, c1 = cell_right(R, seed, long_s, out, "c01_base")
                if want("c01_base"): add(s1, string=long_s, **meta)
            if want("c02_bar"): add(cell_bar(R, seed, c1, out), string=long_s, **meta)
            if want("c03_matched"): add(cell_skyline(R, seed, c1, out), string=long_s, **meta)
            if want("c04_gibberish"):
                g = gibberish(long_s, np.random.default_rng(1000 + i))
                s4, _ = cell_right(R, seed, g, out, "c04_gibberish", note=f"source={long_s}")
                add(s4, string=g, **meta)
            if want("c05_wordgap") or want("c06_decoy"):
                fillers = (row["short"], row["medium"], row["long"])
                ws = seed_word_spacing(R, seed, row["frame"], fillers, row["label"])
                if want("c05_wordgap"): add(cell_wordgap(R, seed, row["frame"], fillers, ws, out), string=row["frame"], **meta)
                if want("c06_decoy"): add(cell_decoy(R, seed, row["frame"], row["medium"], row["label"], ws, out), string=row["frame"], **meta)
            if want("c08_fill"):
                s8, _ = cell_right(R, seed, long_s, out, "c08_fill", boundary="fill")
                add(s8, string=long_s, **meta)
            print(f"P1 row {i} done  {time.time() - t0:6.0f}s", flush=True)

        # ---- P2: pill
        if want("c07_pill"):
            for i in rows:
                s_ = POOLS["P2_en_pill"][i]
                st = style(i, "en", [24, 26, 28], 1.6)
                seed = Seed(f"pill{i:02d}", st["font"], "en", st["fs"], st["text"], st["border"], st["fill"], 0, 0, st["lh"])
                rng = random.Random(f"P2-{i}")
                w, h = measure_box(R, seed, s_)
                r = 1.45 * seed.fs / 2
                seed.x, seed.y = place(rng, w, h, need_right=anchor_extra(w, int(r)) + r, pad=int(r))
                add(cell_pill(R, seed, s_, out), string=s_, pool="P2", row=i, font=st["font"], fs=st["fs"], palette=(i * 2 + i // 5) % 5)
            print(f"P2 done  {time.time() - t0:6.0f}s", flush=True)

        # ---- P3: EN paragraphs -> cell 9
        if want("c09_bottom"):
            for i in rows:
                s_ = POOLS["P3_en_paragraphs"][i]
                st = style(i, "en", [14, 15, 16, 17, 18], 1.45)
                seed = Seed(f"para{i:02d}", st["font"], "en", st["fs"], st["text"], st["border"], st["fill"], 0, 0, st["lh"])
                rng = random.Random(f"P3-{i}")
                bw = [300, 320, 340][i % 3]
                w, h = measure_box(R, seed, s_, width=bw - 2 * (PAD + BORDER))
                seed.x, seed.y = place(rng, w, h, need_bottom=anchor_extra(h))
                add(cell_bottom(R, seed, s_, out, "c09_bottom", bw=bw), string=s_, pool="P3", row=i, font=st["font"], fs=st["fs"], palette=(i * 2 + i // 5) % 5)
            print(f"P3 done  {time.time() - t0:6.0f}s", flush=True)

        # ---- P4: TH single -> cell 10
        if want("c10_thai"):
            for i in rows:
                s_ = POOLS["P4_th_single"][i]
                st = style(i, "th", [18, 20, 22, 24, 20], 1.7)
                seed = Seed(f"th{i:02d}", st["font"], "th", st["fs"], st["text"], st["border"], st["fill"], 0, 0, st["lh"])
                rng = random.Random(f"P4-{i}")
                w, h = measure_box(R, seed, s_)
                seed.x, seed.y = place(rng, w, h, need_right=anchor_extra(w))
                s10, _ = cell_right(R, seed, s_, out, "c10_thai")
                add(s10, string=s_, pool="P4", row=i, font=st["font"], fs=st["fs"], palette=(i * 2 + i // 5) % 5)
            print(f"P4 done  {time.time() - t0:6.0f}s", flush=True)

        # ---- P5: TH marks -> cell 11
        if want("c11_marks"):
            for i in rows:
                row = POOLS["P5_th_marks"][i]
                st = style(i, "th", [20, 22, 24], 1.7)
                seed = Seed(f"thm{i:02d}", st["font"], "th", st["fs"], st["text"], st["border"], st["fill"], 0, 0, st["lh"])
                rng = random.Random(f"P5-{i}")
                w, h = measure_box(R, seed, row["text"])
                top = row["family"] != "below"
                seed.x, seed.y = place(rng, w, h, need_right=anchor_extra(w),
                                       need_top=anchor_extra(h) if top else 0, need_bottom=0 if top else anchor_extra(h))
                add(cell_thai_marks(R, seed, row["text"], row["family"], out), string=row["text"], family=row["family"],
                    pool="P5", row=i, font=st["font"], fs=st["fs"], palette=(i * 2 + i // 5) % 5)
            print(f"P5 done  {time.time() - t0:6.0f}s", flush=True)

        # ---- P6: TH paragraphs -> cell 12
        if want("c12_thaiwrap"):
            for i in rows:
                s_ = POOLS["P6_th_paragraphs"][i]
                st = style(i, "th", [15, 16, 17, 18, 19], 1.6)
                seed = Seed(f"thp{i:02d}", st["font"], "th", st["fs"], st["text"], st["border"], st["fill"], 0, 0, st["lh"])
                rng = random.Random(f"P6-{i}")
                bw = [300, 320, 340][i % 3]
                w, h = measure_box(R, seed, s_, width=bw - 2 * (PAD + BORDER))
                seed.x, seed.y = place(rng, w, h, need_bottom=anchor_extra(h))
                add(cell_bottom(R, seed, s_, out, "c12_thaiwrap", bw=bw), string=s_, pool="P6", row=i, font=st["font"], fs=st["fs"], palette=(i * 2 + i // 5) % 5)
            print(f"P6 done  {time.time() - t0:6.0f}s", flush=True)
    finally:
        R.close()

    mpath = out / "manifest.jsonl"
    if cells is not None and mpath.exists():
        built = {r["cell"] for r in records}
        keep = [json.loads(l) for l in mpath.open(encoding="utf-8")]
        keep = [r for r in keep if r["cell"] not in built and (rows == list(range(15)) or True)]
        if rows != list(range(15)):
            done_ids = {(r["cell"], r["sid"], r["level"]) for r in records}
            old = [json.loads(l) for l in mpath.open(encoding="utf-8")]
            keep = [r for r in old if (r["cell"], r["sid"], r["level"]) not in done_ids]
        records = keep + records
        records.sort(key=lambda r: (r["cell"], r["sid"], r["level"]))
    with open(mpath, "w", encoding="utf-8") as f:
        for d in records:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"wrote {len(records)} records to {out / 'manifest.jsonl'} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="v1")
    ap.add_argument("--cells", default=None)
    ap.add_argument("--rows", default=None)
    a = ap.parse_args()
    cells = set(a.cells.split(",")) if a.cells else None
    rows = [int(r) for r in a.rows.split(",")] if a.rows else list(range(15))
    build(GEN / "out" / a.out, cells, rows)
