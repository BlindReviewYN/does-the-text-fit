"""Render candidate styles for the matched-bar control (cell 3) side by side."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from render import (GEN, LEVELS_RIGHT, W, H, Renderer, Seed, Stim, blobs_from_text, boxes_from_text, finalize,
                    geom_right, render_content, render_text, text_css)

OUT = GEN / "out" / "matched_options"
LEVELS = [("m3", -3), ("p4", 4), ("p12", 12)]


def skyline_from_text(c, color):
    """Per-glyph blobs matched in BOTH ink area and ink height: width = area / height, centred on the glyph."""
    divs = []
    for (l, t, r, b), ch in zip(c.chars, c.string):
        if ch.isspace():
            continue
        L, T, Rr, B = int(math.floor(l)), int(math.floor(t)), int(math.ceil(r)), int(math.ceil(b))
        sub = c.ink[T:B, L:Rr]
        if not sub.any():
            continue
        rows = np.nonzero(sub.any(axis=1))[0]; cols = np.nonzero(sub.any(axis=0))[0]
        gt, gb = T + int(rows.min()), T + int(rows.max())
        h = gb - gt + 1
        area = int(sub.sum())
        w = max(1, int(round(area / h)))
        cx = L + float(np.nonzero(sub)[1].mean())
        left = int(round(cx - w / 2))
        divs.append(f'<div style="position:absolute;left:{left}px;top:{gt}px;width:{w}px;height:{h}px;background:{color}"></div>')
    return "".join(divs)


def greek_from_text(c, seed):
    """One bar per word from the word's ink extent, x-height band above the baseline (placeholder greeking)."""
    from render import word_extents
    base = int(round(c.baseline))
    xh = int(round(0.52 * seed.fs))
    divs = []
    for (l, r) in word_extents(c):
        divs.append(f'<div style="position:absolute;left:{l}px;top:{base - xh}px;width:{r - l + 1}px;height:{xh}px;background:{seed.text}"></div>')
    return "".join(divs)


def variant_stims(R, seed, name, c, tag):
    return [finalize(R, seed, c, "rect", "border", geom_right(c, p), OUT, seed.sid, name, n, p, note=tag)
            for n, p in LEVELS]


def main():
    R = Renderer()
    try:
        seed = Seed("enA", "Inter", "en", 16, x=140, y=250)
        string = "Please review the attached presentation"
        ct = render_text(R, seed, string)
        ink_t = int(ct.ink.sum())
        rows = {}
        rows["text (reference)"] = variant_stims(R, seed, "ref_text", ct, f"ink=1.00x")

        def content(kind, body):
            c = render_content(R, seed, kind, "left:0;top:0;", body)
            c.cbox, c.baseline = ct.cbox, ct.baseline
            return c

        c = content("dashes", blobs_from_text(ct, seed.text)[0])
        rows["A dashes: per glyph, ink-area matched"] = variant_stims(R, seed, "A_dashes", c, f"ink={c.ink.sum()/ink_t:.2f}x")
        c = content("skyline", skyline_from_text(ct, seed.text))
        rows["B skyline: per glyph, ink area AND height matched"] = variant_stims(R, seed, "B_skyline", c, f"ink={c.ink.sum()/ink_t:.2f}x")
        c = content("boxes", boxes_from_text(ct, seed.text)[0])
        rows["C boxes: per glyph, extent matched"] = variant_stims(R, seed, "C_boxes", c, f"ink={c.ink.sum()/ink_t:.2f}x")
        c = content("greek", greek_from_text(ct, seed))
        rows["D greeked words: one x-height bar per word"] = variant_stims(R, seed, "D_greek", c, f"ink={c.ink.sum()/ink_t:.2f}x")
        # E flipped text: same glyphs upside down (false-font rung), paint-only transform
        css = text_css(seed) + "transform:scaleY(-1);"
        import html as _h
        from render import MARKER
        c = render_content(R, seed, "flipped", css, _h.escape(string) + MARKER, string)
        rows["E flipped text: identical glyphs, upside down"] = variant_stims(R, seed, "E_flipped", c, f"ink={c.ink.sum()/ink_t:.2f}x")
    finally:
        R.close()

    font = ImageFont.truetype(str(GEN / "fonts" / "Inter.ttf"), 14)
    tiles_w, tile_h = 3, 0
    crops = []
    for title, stims in rows.items():
        row = []
        for s in stims:
            bx, by, bw, bh = s.geo
            il, it, ir, ib = s.ink_bbox
            x0, y0 = min(bx, il) - 20, min(by, it) - 16
            x1, y1 = max(bx + bw, ir + 1) + 40, max(by + bh, ib + 1) + 16
            row.append((Image.open(s.path).crop((x0, y0, x1, y1)), f"{s.level}  ov={s.cert['overflow_px']}px  eye {s.eye768}/{s.eye512}"))
        crops.append((title, stims[0].note, row))
    tw = max(im.width for _, _, r in crops for im, _ in r) + 12
    th = max(im.height for _, _, r in crops for im, _ in r) + 22
    out = Image.new("RGB", (tiles_w * tw + 12, len(crops) * (th + 30) + 12), "#eeeeee")
    d = ImageDraw.Draw(out)
    y = 8
    for title, note, row in crops:
        d.text((12, y), f"{title}   [{note}]", fill="#111", font=font)
        y += 22
        for i, (im, cap) in enumerate(row):
            x = 12 + i * tw
            d.text((x, y), cap, fill="#444", font=font)
            out.paste(im, (x, y + 18))
            d.rectangle([x - 1, y + 17, x + im.width, y + 18 + im.height], outline="#bbbbbb")
        y += th + 8
    out.save(OUT / "matched_options.png")
    print("saved", OUT / "matched_options.png", out.size)


if __name__ == "__main__":
    main()
