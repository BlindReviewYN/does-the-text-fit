"""Render one seed per cell at every level, write manifest + montages for eyeballing."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from render import (BORDER, GEN, H, LEVELS_RIGHT, PAD, W, Content, Renderer, Seed, Stim, bar_from_text,
                    blobs_from_text, boxes_from_text, certify, finalize, geom_bottom, geom_right, geom_top, gibberish,
                    make_mask, pill_h_clearance, render_content, render_text, strip_marks, word_extents)

OUT = GEN / "out" / "samples"
NEG3 = [("anchor", "anchor"), ("m10", -10), ("m3", -3)]


# ----------------------------------------------------------------------------- cells

def cell_right(R, seed, string, cell, boundary="border", levels=LEVELS_RIGHT):
    c = render_text(R, seed, string)
    return [finalize(R, seed, c, "rect", boundary, geom_right(c, p), OUT, seed.sid, cell, n, p) for n, p in levels], c


def cell_bar(R, seed, c_text, cell="c02_bar"):
    body, mask = bar_from_text(c_text, seed)
    c = render_content(R, seed, "bar", "left:0;top:0;", body)
    c.cbox, c.baseline = c_text.cbox, c_text.baseline
    return [finalize(R, seed, c, "rect", "border", geom_right(c, p), OUT, seed.sid, cell, n, p) for n, p in LEVELS_RIGHT]


def cell_matched(R, seed, c_text, cell="c03_matched"):
    body, mask = blobs_from_text(c_text, seed.text)
    c = render_content(R, seed, "blobs", "left:0;top:0;", body)
    c.cbox, c.baseline = c_text.cbox, c_text.baseline
    note = f"text_ink={int(c_text.ink.sum())};blob_ink={int(c.ink.sum())}"
    return [finalize(R, seed, c, "rect", "border", geom_right(c, p), OUT, seed.sid, cell, n, p, note=note)
            for n, p in LEVELS_RIGHT]


def _gapped(R, seed, base, label_span=None, need=9, ws=None):
    """Render base (+ label) with word-spacing raised until the last inter-word ink gap >= need px.
    Pass ws to force a seed-wide word-spacing (so fit and spill items share spacing)."""
    if ws is None:
        c = render_text(R, seed, base, label_span=label_span)
        we = word_extents(c)
        gap = we[-1][0] - we[-2][1] - 1
        ws = max(0, need - gap)
    c = render_text(R, seed, base, word_spacing=ws, label_span=label_span)
    we = word_extents(c)
    return c, we, ws


def seed_word_spacing(R, seed, frame, fillers, label, need=9):
    """One word-spacing per seed: the max needed over all cell-5/6 strings."""
    ws = 0
    for f in list(fillers) + [label]:
        _, _, w = _gapped(R, seed, f"{frame} {f}", need=need)
        ws = max(ws, w)
    return ws


def cell_wordgap(R, seed, frame, fillers, ws, cell="c05_wordgap"):
    stims = []
    c_med = render_text(R, seed, f"{frame} {fillers[1]}", word_spacing=ws)
    for n, p in NEG3:
        stims.append(finalize(R, seed, c_med, "rect", "border", geom_right(c_med, p), OUT, seed.sid, cell, n, p,
                              note=f"word_spacing={ws}"))
    for n, filler in zip(["short", "medium", "long"], fillers):
        c, we, _ = _gapped(R, seed, f"{frame} {filler}", ws=ws)
        pen_r, last_l = we[-2][1], we[-1][0]
        last_col = pen_r + 3 + BORDER
        bx, by, _, bh = geom_right(c, 0)
        geo = (bx, by, last_col - bx + 1, bh)
        stims.append(finalize(R, seed, c, "rect", "border", geo, OUT, seed.sid, cell, n, f"gap{last_l - last_col - 1}",
                              note=f"word={filler};word_spacing={ws}"))
    return stims


def cell_decoy(R, seed, frame, medium, label, ws, cell="c06_decoy"):
    stims = []
    for comp in ["incomplete", "complete"]:
        base = frame if comp == "incomplete" else f"{frame} {medium}"
        c0, we, _ = _gapped(R, seed, base, label_span=(label, 0), ws=ws)
        pen_r, last_l = we[-2][1], we[-1][0]
        last_col = pen_r + 3 + BORDER
        twin_gap = last_l - last_col - 1
        for gname, g in [("gTwin", twin_gap), ("g12", 12), ("g30", 30)]:
            extra = g - twin_gap
            c = c0 if extra == 0 else render_text(R, seed, base, word_spacing=ws, label_span=(label, extra))
            bx, by, _, bh = geom_right(c, 0)
            geo = (bx, by, last_col - bx + 1, bh)
            mg = word_extents(c)[-1][0] - last_col - 1
            stims.append(finalize(R, seed, c, "rect", "border", geo, OUT, seed.sid, cell, f"{comp}_{gname}", g,
                                  label_rule="no", note=f"min_gap={mg};label={label}"))
    return stims


def cell_boxes(R, seed, c_text, cell="c03b_boxes"):
    body, mask = boxes_from_text(c_text, seed.text)
    c = render_content(R, seed, "boxes", "left:0;top:0;", body)
    c.cbox, c.baseline = c_text.cbox, c_text.baseline
    note = f"text_ink={int(c_text.ink.sum())};box_ink={int(c.ink.sum())}"
    return [finalize(R, seed, c, "rect", "border", geom_right(c, p), OUT, seed.sid, cell, n, p, note=note)
            for n, p in LEVELS_RIGHT]


def cell_pill(R, seed, string, cell="c07_pill", ratio=1.6):
    c = render_text(R, seed, string)
    l, t, r, b = c.cbox
    bh = int(round(ratio * seed.fs))
    by = int(round((t + b) / 2 - bh / 2))
    bx = int(math.floor(l)) - int(round(bh / 2))
    ir = c.bbox[2]
    bw0 = ir - bx + 1                      # ink_right in the bbox's last column
    levels = []
    for n, target in [("m3", 3), ("m10", 10)]:
        bw = bw0
        while pill_h_clearance(c.ink, bx, by, bw, bh) < target and bw < bw0 + 120:
            bw += 1
        levels.append((n, f"clear{target}", bw))
    levels = [("anchor", "anchor", int(round(bw0 / 0.6)))] + levels
    levels += [("corner", "corner", bw0), ("p4", 4, bw0 - 4), ("p12", 12, bw0 - 12)]
    return [finalize(R, seed, c, "pill", "fill", (bx, by, bw, bh), OUT, seed.sid, cell, n, p,
                     extra_cert={"h_clearance": pill_h_clearance(c.ink, bx, by, bw, bh)}) for n, p, bw in levels]


def cell_bottom(R, seed, paragraph, cell, bw=320):
    tw = bw - 2 * (PAD + BORDER)
    c = render_text(R, seed, paragraph, width=tw)
    bx = int(math.floor(c.cbox[0])) - PAD - BORDER
    return [finalize(R, seed, c, "rect", "border", geom_bottom(c, p, bx, bw), OUT, seed.sid, cell, n, p)
            for n, p in LEVELS_RIGHT]


def cell_thai_marks(R, seed, string, family, cell="c11P_marks"):
    c = render_text(R, seed, string)
    cb = render_text(R, seed, strip_marks(string))
    bx, by, bw, bh = geom_right(c, "anchor")
    stims = []
    if family != "below":
        it, it_base = c.bbox[1], cb.bbox[1]
        note = f"mark_height={it_base - it}"
        for n, p in [("anchor", "anchor"), ("m3", -3), ("m1", -1), ("p3", 3), ("p6", 6), ("p9", 9)]:
            stims.append(finalize(R, seed, c, "rect", "border", geom_top(c, p, bx, bw), OUT, seed.sid, cell,
                                  f"{family}_{n}", p, note=note))
    else:
        ib, ib_base = c.bbox[3], cb.bbox[3]
        note = f"mark_depth={ib - ib_base}"
        for n, p in [("anchor", "anchor"), ("m3", -3), ("m1", -1), ("p3", 3), ("p6", 6), ("p9", 9)]:
            stims.append(finalize(R, seed, c, "rect", "border", geom_bottom(c, p, bx, bw), OUT, seed.sid, cell,
                                  f"{family}_{n}", p, note=note))
    return stims, c, cb


def cell_thai_clip(R, seed, string, family, c, cb, cell="c11C_clip"):
    bx, by, bw, bh = geom_right(c, "anchor")
    stims = []
    if family != "below":
        it, it_base = c.bbox[1], cb.bbox[1]
        bottom_row = int(math.ceil(c.cbox[3])) + PAD + BORDER
        for n, clip_row in [("intact", None), ("near", it - 1), ("clip3", it + 3), ("clip6", it + 6)]:
            if clip_row is None:
                cc, geo, removed = c, geom_top(c, "anchor", bx, bw), 0
            else:
                cc = render_text(R, seed, string, clip_top=clip_row - c.cbox[1])
                top_row = clip_row - BORDER
                geo = (bx, top_row, bw, bottom_row - top_row + 1)
                removed = int(c.ink[:clip_row].sum())
            eye = (int(removed * 0.75 ** 2), int(removed * 0.5 ** 2))
            pname = "none" if clip_row is None else str(clip_row - it)
            stims.append(finalize(R, seed, cc, "rect", "border", geo, OUT, seed.sid, cell, f"{family}_{n}",
                                  "clip" + pname, label_rule="yes" if removed >= 1 else "no",
                                  extra_cert={"removed_px": removed}, eye_override=eye,
                                  note=f"mark_height={it_base - it}"))
    return stims


# ----------------------------------------------------------------------------- montage

def montage(groups: dict[str, list[Stim]], path: Path, cols=3):
    font = ImageFont.truetype(str(GEN / "fonts" / "Inter.ttf"), 13)
    rows = []
    for cell, stims in groups.items():
        tiles = []
        for s in stims:
            bx, by, bw, bh = s.geo
            il, it, ir, ib = s.ink_bbox
            x0, y0 = max(min(bx, il) - 24, 0), max(min(by, it) - 20, 0)
            x1, y1 = min(max(bx + bw, ir + 1) + 24, W), min(max(by + bh, ib + 1) + 20, H)
            crop = Image.open(s.path).crop((x0, y0, x1, y1))
            extra = "".join(f" {k}={v}" for k, v in s.cert.items() if k in ("h_clearance", "removed_px"))
            cap = (f"{s.level} | p={s.p} | {s.label} | ov={s.cert['overflow_px']}px pen={s.cert['penetration']} "
                   f"clr={s.cert['clearance']}{extra} | eye {s.eye768}/{s.eye512}" + (" SUB-RES" if s.sub_resolution else ""))
            tiles.append((crop, cap))
        tw = max(max(t[0].width for t in tiles) + 16, 560)
        th = max(t[0].height for t in tiles) + 40
        nrows = math.ceil(len(tiles) / cols)
        row = Image.new("RGB", (cols * tw, nrows * th), "#f0f0f0")
        d = ImageDraw.Draw(row)
        for i, (crop, cap) in enumerate(tiles):
            cx, cy = (i % cols) * tw, (i // cols) * th
            d.text((cx + 8, cy + 6), cap, fill="#333", font=font)
            row.paste(crop, (cx + 8, cy + 26))
            d.rectangle([cx + 7, cy + 25, cx + 8 + crop.width, cy + 26 + crop.height], outline="#bbbbbb")
        rows.append(row)
    Wm = max(r.width for r in rows)
    out = Image.new("RGB", (Wm, sum(r.height + 12 for r in rows)), "#d9d9d9")
    y = 0
    for r in rows:
        out.paste(r, (0, y)); y += r.height + 12
    out.save(path)
    return path


# ----------------------------------------------------------------------------- main

def main():
    R = Renderer()
    all_stims: dict[str, list[Stim]] = {}
    try:
        en = Seed("enA", "Inter", "en", 16, x=140, y=250)
        frame, fillers = "Please review the attached", ("file", "document", "presentation")
        s1, c1 = cell_right(R, en, f"{frame} {fillers[2]}", "c01_base")
        all_stims["c01_base"] = s1
        all_stims["c02_bar"] = cell_bar(R, en, c1)
        all_stims["c03_matched"] = cell_matched(R, en, c1)
        all_stims["c03b_boxes"] = cell_boxes(R, en, c1)
        rng = np.random.default_rng(7)
        all_stims["c04_gibberish"], _ = cell_right(R, en, gibberish(f"{frame} {fillers[2]}", rng), "c04_gibberish")
        ws = seed_word_spacing(R, en, frame, fillers, "Settings")
        all_stims["c05_wordgap"] = cell_wordgap(R, en, frame, fillers, ws)
        all_stims["c06_decoy"] = cell_decoy(R, en, frame, fillers[1], "Settings", ws)
        pill = Seed("pillA", "Inter", "en", 20, x=140, y=250)
        all_stims["c07_pill"] = cell_pill(R, pill, "Payment method")
        pill2 = Seed("pillB", "Inter", "en", 28, x=140, y=250)
        all_stims["c07b_pill28"] = cell_pill(R, pill2, "Payment method", cell="c07b_pill28", ratio=1.45)
        all_stims["c08_fill"], _ = cell_right(R, en, f"{frame} {fillers[2]}", "c08_fill", boundary="fill")
        para = Seed("paraA", "Roboto", "en", 16, x=140, y=200, lh=1.45)
        all_stims["c09_bottom"] = cell_bottom(
            R, para, "Your subscription will renew automatically at the end of the billing period unless you cancel "
                     "at least one day before the renewal date.", "c09_bottom")
        th = Seed("thA", "Sarabun", "th", 20, x=140, y=250)
        all_stims["c10_thai"], _ = cell_right(R, th, "กรุณาตรวจสอบเอกสารแนบก่อนส่ง", "c10_thai")
        thm = Seed("thM", "NotoSansThai", "th", 22, x=140, y=250, lh=1.7)
        marks = [("single", "ก่อนส่งข้อความ"), ("stacked", "ที่นี่ไม่มีใคร"), ("tall", "ฟ้าใสมาก"), ("below", "ครูพาลูกดูงู")]
        p_all, c_all = [], []
        for fam, s in marks:
            st, c, cb = cell_thai_marks(R, thm, s, fam)
            p_all += st
            if fam in ("stacked", "tall"):
                c_all += cell_thai_clip(R, thm, s, fam, c, cb)
        all_stims["c11P_marks"] = p_all
        all_stims["c11C_clip"] = c_all
        thp = Seed("thP", "Prompt", "th", 16, x=140, y=200, lh=1.6)
        all_stims["c12_thaiwrap"] = cell_bottom(
            R, thp, "ระบบจะต่ออายุการสมัครสมาชิกโดยอัตโนมัติเมื่อสิ้นสุดรอบการเรียกเก็บเงิน "
                    "เว้นแต่คุณจะยกเลิกล่วงหน้าอย่างน้อยหนึ่งวันก่อนวันต่ออายุ", "c12_thaiwrap")
    finally:
        R.close()

    with open(OUT / "manifest.jsonl", "w", encoding="utf-8") as f:
        for cell, stims in all_stims.items():
            for s in stims:
                d = s.__dict__.copy(); d["geo"] = list(s.geo)
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
    for cell, stims in all_stims.items():
        for s in stims:
            print(f"{cell:14s} {s.level:22s} p={s.p:8s} lbl={s.label:3s} ov={s.cert['overflow_px']:5d} "
                  f"pen={s.cert['penetration']:5.1f} clr={s.cert['clearance']:5.1f} eye768={s.eye768:4d} eye512={s.eye512:4d}"
                  f"{'  SUB' if s.sub_resolution else ''}  {s.note}")
    groups = [["c01_base", "c02_bar", "c03_matched", "c03b_boxes", "c04_gibberish"],
              ["c05_wordgap", "c06_decoy", "c07_pill", "c07b_pill28", "c08_fill"],
              ["c09_bottom", "c10_thai", "c12_thaiwrap"], ["c11P_marks", "c11C_clip"]]
    for i, g in enumerate(groups, 1):
        montage({k: all_stims[k] for k in g}, OUT / f"montage_{i}.png")
    print("done", OUT)


if __name__ == "__main__":
    main()
