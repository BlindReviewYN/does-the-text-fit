"""Render candidate decoy designs for cell 6 side by side (two seeds, twin gap and 12 px)."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render import BORDER, GEN, W, H, Renderer, Seed, finalize, geom_right, render_text, word_extents

OUT = GEN / "out" / "decoy_options"

VARIANTS = [
    ("V1 current: same style, noun label", "Settings", ""),
    ("V2 same style, control word that cannot continue the sentence", "Cancel", ""),
    ("V3 bordered button, same font and colour", "Cancel", "border:2px solid currentColor;border-radius:4px;padding:1px 8px;"),
    ("V4 bordered button, raised half a line (own baseline)", "Cancel", "border:2px solid currentColor;border-radius:4px;padding:1px 8px;position:relative;top:-9px;"),
    ("V5 grey hint text, smaller, own baseline", "optional", "color:#7a8194;font-size:0.8em;position:relative;top:-1px;"),
]


def decoy(R, seed, frame, medium, label, style, gap_name, gap, comp, out, cell):
    base = frame if comp == "incomplete" else f"{frame} {medium}"
    ws = 3
    c0 = render_text(R, seed, base, word_spacing=ws, label_span=(label, 0, style))
    we = word_extents(c0)
    pen_r, last_l = we[-2][1], we[-1][0]
    last_col = pen_r + 3 + BORDER
    twin_gap = last_l - last_col - 1
    extra = 0 if gap == "twin" else gap - twin_gap
    c = c0 if extra == 0 else render_text(R, seed, base, word_spacing=ws, label_span=(label, extra, style))
    bx, by, _, bh = geom_right(c, 0)
    geo = (bx, by, last_col - bx + 1, bh)
    mg = word_extents(c)[-1][0] - last_col - 1
    return finalize(R, seed, c, "rect", "border", geo, out, seed.sid, cell, f"{comp}_{gap_name}", gap, label_rule="no",
                    extra_cert={"min_gap": mg})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    R = Renderer()
    rows = []
    try:
        seeds = [(Seed("en00", "Inter", "en", 16, x=140, y=250), "Please review the attached", "document"),
                 (Seed("en04", "Roboto", "en", 18, x=140, y=250), "The meeting notes are available in the", "archive")]
        for vi, (title, label, style) in enumerate(VARIANTS):
            tiles = []
            for seed, frame, medium in seeds:
                for comp in ("incomplete", "complete"):
                    for gname, g in (("twin", "twin"), ("g12", 12)):
                        tiles.append(decoy(R, seed, frame, medium, label, style, gname, g, comp, OUT, f"decoy_V{vi + 1}"))
            rows.append((title, tiles))
    finally:
        R.close()
    font = ImageFont.truetype(str(GEN / "fonts" / "Inter.ttf"), 14)
    crops = []
    for title, tiles in rows:
        imgs = []
        for s in tiles:
            bx, by, bw, bh = s.geo; il, it, ir, ib = s.ink_bbox
            x0, y0 = min(bx, il) - 14, min(by, it) - 12
            x1, y1 = max(bx + bw, ir + 1) + 14, max(by + bh, ib + 1) + 12
            imgs.append((Image.open(s.path).crop((x0, y0, x1, y1)), f"{s.level}  gap {s.cert['min_gap']}"))
        crops.append((title, imgs))
    cols = 4
    tw = max(im.width for _, imgs in crops for im, _ in imgs) + 12
    th = max(im.height for _, imgs in crops for im, _ in imgs) + 22
    rows_per = math.ceil(len(crops[0][1]) / cols)
    out = Image.new("RGB", (cols * tw + 12, len(crops) * (rows_per * th + 34) + 12), "#eeeeee")
    d = ImageDraw.Draw(out)
    y = 8
    for title, imgs in crops:
        d.text((12, y), title, fill="#111", font=font); y += 24
        for i, (im, cap) in enumerate(imgs):
            x = 12 + (i % cols) * tw; yy = y + (i // cols) * th
            d.text((x, yy), cap, fill="#555", font=font)
            out.paste(im, (x, yy + 18))
            d.rectangle([x - 1, yy + 17, x + im.width, yy + 18 + im.height], outline="#bbbbbb")
        y += rows_per * th + 10
    out.save(OUT / "decoy_options.png")
    print(OUT / "decoy_options.png", out.size)


if __name__ == "__main__":
    main()
