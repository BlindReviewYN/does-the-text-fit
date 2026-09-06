"""Stimulus renderer v0 for the text-overflow benchmark.

Pipeline per seed:
  1. render the content layer alone (text / bar / blobs) -> ink mask, char rects, baseline
  2. compute box geometry for every level in numpy from the ink (never from advance widths)
  3. render the final image (box + content) once per level
  4. certify: analytic inside mask (rect / capsule), overflow px, penetration, clearance,
     model-eye survival at 768 and 512 wide

Text and box are independent absolutely-positioned layers: changing the box never reflows the text.
"""
from __future__ import annotations

import html
import io
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt as edt
from playwright.sync_api import sync_playwright

W, H = 1024, 640
GEN = Path(__file__).resolve().parent
WORK = GEN / "out" / "_work"
WORK.mkdir(parents=True, exist_ok=True)
BORDER = 2          # px, border cells
PAD = 10            # px, inner padding from the border's inner edge
FONTS = {
    "Inter": "Inter.ttf", "Roboto": "Roboto.ttf", "SourceSans3": "SourceSans3.ttf", "OpenSans": "OpenSans.ttf",
    "Sarabun": "Sarabun.ttf", "NotoSansThai": "NotoSansThai.ttf", "Prompt": "Prompt.ttf",
}
THAI_MARKS = set("ัิีึืฺุู็่้๊๋์ํ๎")


def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def hex_lum(col: str) -> float:
    r, g, b = int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def ink_threshold(text_color: str) -> float:
    """Pixel counts as ink at >= 50 % coverage of the text colour over white."""
    return (255.0 + hex_lum(text_color)) / 2.0


# ----------------------------------------------------------------------------- browser

class Renderer:
    def __init__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self.page = self._browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)

    def close(self):
        self._browser.close()
        self._pw.stop()

    def load(self, page_html: str):
        f = WORK / "page.html"
        f.write_text(page_html, encoding="utf-8")
        self.page.goto(f.as_uri())
        self.page.evaluate("document.fonts.ready")
        self.page.wait_for_function("document.fonts.status === 'loaded'")

    def measure_only(self, page_html: str) -> dict:
        self.load(page_html)
        return self.measure()

    def shot(self) -> np.ndarray:
        png = self.page.screenshot(type="png")
        return np.array(Image.open(io.BytesIO(png)).convert("RGB"))

    def measure(self) -> dict:
        return self.page.evaluate(
            """() => {
              const el = document.getElementById('content');
              const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
              const r = document.createRange(); const chars = []; let n;
              while ((n = walker.nextNode())) {
                for (let i = 0; i < n.length; i++) {
                  r.setStart(n, i); r.setEnd(n, i + 1);
                  const b = r.getBoundingClientRect();
                  chars.push([b.left, b.top, b.right, b.bottom]);
                }
              }
              const bl = document.getElementById('bl');
              const cb = el.getBoundingClientRect();
              return {chars, baseline: bl ? bl.getBoundingClientRect().bottom : null,
                      cbox: [cb.left, cb.top, cb.right, cb.bottom]};
            }"""
        )


def page_html(font: str, lang: str, content_css: str, content_html: str,
              box_css: str = "", box_visible: bool = False, content_visible: bool = True) -> str:
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><style>
@font-face{{font-family:'F';src:url('../../fonts/{FONTS[font]}');}}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#ffffff}}
#box{{position:absolute;box-sizing:border-box;z-index:1;visibility:{'visible' if box_visible else 'hidden'};{box_css}}}
#content{{position:absolute;z-index:2;font-family:'F';visibility:{'visible' if content_visible else 'hidden'};{content_css}}}
</style></head><body><div id="box"></div><div id="content">{content_html}</div></body></html>"""


MARKER = '<span id="bl" style="display:inline-block;width:0;height:0"></span>'


# ----------------------------------------------------------------------------- content specs

@dataclass
class Seed:
    sid: str
    font: str
    lang: str
    fs: int
    text: str = "#111111"
    border: str = "#222222"
    fill: str = "#dfe7f3"
    x: int = 120           # text left (page px)
    y: int = 260           # content element top (page px)
    lh: float = 1.6


@dataclass
class Content:
    """One rendered content layer (text-only pass)."""
    kind: str                       # text | bar | blobs
    css: str
    html: str
    img: np.ndarray                 # RGB text-only render
    ink: np.ndarray                 # bool mask
    chars: list                     # advance rects per char (page px)
    cbox: list                      # content element rect
    baseline: float | None
    string: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def bbox(self):
        ys, xs = np.nonzero(self.ink)
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def text_css(seed: Seed, width: int | None = None, word_spacing: float = 0, clip_top: float | None = None,
             x: int | None = None) -> str:
    x = seed.x if x is None else x
    css = (f"left:{x}px;top:{seed.y}px;font-size:{seed.fs}px;line-height:{seed.lh};color:{seed.text};"
           f"word-spacing:{word_spacing}px;")
    css += f"width:{width}px;white-space:normal;" if width else "white-space:nowrap;"
    if clip_top is not None:
        css += f"clip-path:inset({clip_top}px 0 0 0);"
    return css


def render_content(R: Renderer, seed: Seed, kind: str, css: str, content_html: str, string: str = "") -> Content:
    R.load(page_html(seed.font, seed.lang, css, content_html))
    m = R.measure()
    img = R.shot()
    ink = luminance(img) < ink_threshold(seed.text)
    return Content(kind, css, content_html, img, ink, m["chars"], m["cbox"], m["baseline"], string)


def render_text(R: Renderer, seed: Seed, string: str, width: int | None = None, word_spacing: float = 0,
                clip_top: float | None = None, label_span: tuple[str, float] | None = None) -> Content:
    """label_span = (label, extra_margin_px): render `string + ' ' + label` with the label in its own span."""
    if label_span:
        label, extra = label_span[0], label_span[1]
        style = label_span[2] if len(label_span) > 2 else ""
        body = html.escape(string + " ") + f'<span style="margin-left:{extra}px;{style}">{html.escape(label)}</span>'
        full = string + " " + label
    else:
        body, full = html.escape(string), string
    css = text_css(seed, width, word_spacing, clip_top)
    return render_content(R, seed, "text", css, body + MARKER, full)


def word_extents(c: Content) -> list[tuple[int, int]]:
    """Ink (left, right) columns per space-separated word, from char advance rects ∩ ink."""
    out, i = [], 0
    for w in c.string.split(" "):
        idx = list(range(i, i + len(w)))
        i += len(w) + 1
        if not w:
            continue
        rects = [c.chars[j] for j in idx]
        l = int(math.floor(min(r[0] for r in rects))); r_ = int(math.ceil(max(r[2] for r in rects)))
        t = int(math.floor(min(r[1] for r in rects))); b = int(math.ceil(max(r[3] for r in rects)))
        sub = c.ink[t:b, l:r_]
        cols = np.nonzero(sub.any(axis=0))[0]
        out.append((l + int(cols.min()), l + int(cols.max())) if len(cols) else (l, l))
    return out


# ----------------------------------------------------------------------------- masks & certificates

def make_mask(shape: str, bx: float, by: float, bw: float, bh: float, dims=(H, W)) -> np.ndarray:
    h, w = dims
    if shape == "rect":
        m = np.zeros((h, w), bool)
        m[int(round(by)):int(round(by + bh)), int(round(bx)):int(round(bx + bw))] = True
        return m
    # capsule: pixel centres inside the stadium
    r = bh / 2.0
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = xx + 0.5 - bx, yy + 0.5 - by
    body = (cx >= r) & (cx <= bw - r) & (cy >= 0) & (cy <= bh)
    left = (cx - r) ** 2 + (cy - r) ** 2 <= r * r
    right = (cx - (bw - r)) ** 2 + (cy - r) ** 2 <= r * r
    return body | left | right


def certify(ink: np.ndarray, inside: np.ndarray, clearance_region: np.ndarray | None = None) -> dict:
    """overflow px, max penetration beyond the outer edge, min clearance inside (px, edge-referenced).

    clearance_region: optional bool mask; clearance is then measured only to outside pixels inside it
    (the pill uses the right-cap zone, since its vertical clearance is capped by the capsule height)."""
    ys, xs = np.nonzero(ink | inside)
    y0, y1, x0, x1 = max(ys.min() - 4, 0), min(ys.max() + 5, ink.shape[0]), max(xs.min() - 4, 0), min(xs.max() + 5, ink.shape[1])
    ink_c, in_c = ink[y0:y1, x0:x1], inside[y0:y1, x0:x1]
    out_c = ~in_c
    ov = ink_c & out_c
    n_out, n_ink = int(ov.sum()), int(ink_c.sum())
    pen = float(edt(out_c)[ov].max()) if n_out else 0.0
    if n_ink and not n_out:
        if clearance_region is None:
            clr = float(edt(in_c)[ink_c].min() - 1)
        else:
            reg = clearance_region[y0:y1, x0:x1]
            clr = float(edt(~(out_c & reg))[ink_c].min() - 1)
    else:
        clr = 0.0
    return {"ink_px": n_ink, "overflow_px": n_out, "penetration": round(pen, 2), "clearance": round(clr, 2)}


def pill_h_clearance(ink: np.ndarray, bx: int, by: int, bw: int, bh: int) -> int:
    """Min over ink rows of (last inside column on the right cap curve) - (rightmost ink column).
    -1 if any ink row lies outside the capsule's vertical range."""
    r = bh / 2.0
    cxr = bx + bw - r
    ys, xs = np.nonzero(ink)
    best = None
    for y in np.unique(ys):
        dy = (y + 0.5) - (by + r)
        if abs(dy) > r:
            return -1
        half = math.sqrt(r * r - dy * dy)
        last_in = int(math.floor(cxr + half - 0.5))
        clr = last_in - int(xs[ys == y].max())
        best = clr if best is None else min(best, clr)
    return int(best)


def model_eye(c: Content, shape: str, geo: tuple, thr: float, scale: float) -> int:
    w, h = int(round(W * scale)), int(round(H * scale))
    small = np.array(Image.fromarray(c.img).resize((w, h), Image.BOX))
    ink = luminance(small) < thr
    bx, by, bw, bh = geo
    inside = make_mask(shape, bx * scale, by * scale, bw * scale, bh * scale, dims=(h, w))
    return int((ink & ~inside).sum())


# ----------------------------------------------------------------------------- box geometry

def box_css(shape: str, boundary: str, seed: Seed, bx: int, by: int, bw: int, bh: int) -> str:
    css = f"left:{bx}px;top:{by}px;width:{bw}px;height:{bh}px;"
    if shape == "pill":
        css += f"border-radius:{bh / 2}px;"
    if boundary == "border":
        css += f"border:{BORDER}px solid {seed.border};background:transparent;"
    else:
        css += f"border:none;background:{seed.fill};"
    return css


def frame_rect(c: Content, pad: int = PAD + BORDER) -> tuple[int, int, int, int]:
    """Box left/top and the ink extents: bx, by, and full height for single-line content."""
    l, t, r, b = c.cbox
    bx = int(math.floor(l)) - pad
    by = int(math.floor(t)) - pad
    bh = int(math.ceil(b)) - int(math.floor(t)) + 2 * pad
    return bx, by, bh, int(math.ceil(r)) + pad


MARGIN = 60   # px, minimum distance from any box edge to the canvas edge


def geom_right(c: Content, p, ink_right: int | None = None) -> tuple[int, int, int, int]:
    """Rect whose right outer edge sits at ink_right - p. p='anchor' -> 40 % margin (capped at the canvas margin)."""
    bx, by, bh, _ = frame_rect(c)
    ir = c.bbox[2] if ink_right is None else ink_right
    if p == "anchor":
        bw = min(int(round((ir - bx + 1) / 0.6)), W - MARGIN - bx)
    else:
        bw = ir - p - bx + 1
    return bx, by, bw, bh


def geom_bottom(c: Content, p, bx: int, bw: int) -> tuple[int, int, int, int]:
    _, by, _, _ = frame_rect(c)
    ib = c.bbox[3]
    if p == "anchor":
        bh = min(int(round((ib - by + 1) / 0.6)), H - MARGIN - by)
    else:
        bh = ib - p - by + 1
    return bx, by, bw, bh


def geom_top(c: Content, p, bx: int, bw: int, ink_top: int | None = None) -> tuple[int, int, int, int]:
    """Top edge manipulated: box first row = ink_top + p (p>0: ink protrudes above)."""
    _, _, _, _ = frame_rect(c)
    it = c.bbox[1] if ink_top is None else ink_top
    bottom_row = int(math.ceil(c.cbox[3])) + PAD + BORDER   # fixed
    if p == "anchor":
        bh = min(int(round((bottom_row - it + 1) / 0.6)), bottom_row - MARGIN + 1)
        top_row = bottom_row - bh + 1
    else:
        top_row = it + p
        bh = bottom_row - top_row + 1
    return bx, top_row, bw, bh


# ----------------------------------------------------------------------------- stimulus assembly

@dataclass
class Stim:
    sid: str
    cell: str
    level: str
    p: str
    shape: str
    boundary: str
    geo: tuple
    label: str
    cert: dict
    eye768: int
    eye512: int
    sub_resolution: bool
    path: str
    seed: dict
    note: str = ""
    ink_bbox: tuple = ()


def finalize(R: Renderer, seed: Seed, c: Content, shape: str, boundary: str, geo: tuple, out: Path,
             sid: str, cell: str, level: str, p, label_rule: str = "overflow", note: str = "",
             content_css: str | None = None, content_html: str | None = None, ink_override=None,
             extra_cert: dict | None = None, eye_override: tuple | None = None) -> Stim:
    bx, by, bw, bh = geo
    inside = make_mask(shape, bx, by, bw, bh)
    ink = c.ink if ink_override is None else ink_override
    cert = certify(ink, inside)
    if extra_cert:
        cert.update(extra_cert)
    thr = ink_threshold(seed.text)
    if eye_override is None:
        e768, e512 = model_eye(c, shape, geo, thr, 0.75), model_eye(c, shape, geo, thr, 0.5)
    else:
        e768, e512 = eye_override
    if label_rule == "overflow":
        label = "yes" if cert["overflow_px"] >= 1 else "no"
    elif label_rule == "no":
        label = "no"
    else:
        label = label_rule  # explicit
    css = content_css if content_css is not None else c.css
    body = content_html if content_html is not None else c.html
    R.load(page_html(seed.font, seed.lang, css, body, box_css(shape, boundary, seed, bx, by, bw, bh), box_visible=True))
    img = R.shot()
    fn = f"{cell}_{level}_{sid}.png"
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(out / fn)
    sub = (label == "yes") and (e768 < 2)
    return Stim(sid, cell, level, str(p), shape, boundary, (bx, by, bw, bh), label, cert, e768, e512, sub,
                str(out / fn), asdict(seed), note, tuple(int(v) for v in c.bbox))


LEVELS_RIGHT = [("anchor", "anchor"), ("m10", -10), ("m3", -3), ("p4", 4), ("p12", 12), ("p30", 30)]


def gibberish(s: str, rng: np.random.Generator) -> str:
    out = []
    for w in s.split(" "):
        m = re.match(r"^([A-Za-z]+)(.*)$", w)
        if not m or len(m.group(1)) < 2:
            out.append(w); continue
        core, tail = m.group(1), m.group(2)
        letters = list(core.lower())
        for _ in range(100):
            rng.shuffle(letters)
            cand = "".join(letters)
            if cand != core.lower():
                break
        if core[0].isupper():
            cand = cand[0].upper() + cand[1:]
        out.append(cand + tail)
    return " ".join(out)


def blobs_from_text(c: Content, color: str) -> tuple[str, np.ndarray]:
    """Per-glyph ink-area-matched rectangles. Returns content html + its ink mask (analytic)."""
    divs, mask = [], np.zeros_like(c.ink)
    for (l, t, r, b), ch in zip(c.chars, c.string):
        if ch.isspace():
            continue
        L, T, Rr, B = int(math.floor(l)), int(math.floor(t)), int(math.ceil(r)), int(math.ceil(b))
        sub = c.ink[T:B, L:Rr]
        if not sub.any():
            continue
        cols = np.nonzero(sub.any(axis=0))[0]
        gl, gr = L + int(cols.min()), L + int(cols.max())
        area = int(sub.sum())
        rows = np.nonzero(sub)[0] + T
        cy = float(rows.mean())
        w = gr - gl + 1
        h = max(1, int(round(area / w)))
        top = int(round(cy - h / 2))
        divs.append(f'<div style="position:absolute;left:{gl}px;top:{top}px;width:{w}px;height:{h}px;background:{color}"></div>')
        mask[top:top + h, gl:gl + w] = True
    return "".join(divs), mask


def skyline_from_text(c: Content, color: str) -> str:
    """Per-glyph blobs matched in BOTH ink area and ink height: width = area / height, centred on the glyph."""
    divs = []
    for (l, t, r, b), ch in zip(c.chars, c.string):
        if ch.isspace():
            continue
        L, T, Rr, B = int(math.floor(l)), int(math.floor(t)), int(math.ceil(r)), int(math.ceil(b))
        sub = c.ink[T:B, L:Rr]
        if not sub.any():
            continue
        rows = np.nonzero(sub.any(axis=1))[0]
        gt, gb = T + int(rows.min()), T + int(rows.max())
        h = gb - gt + 1
        area = int(sub.sum())
        w = max(1, int(round(area / h)))
        cx = L + float(np.nonzero(sub)[1].mean())
        left = int(round(cx - w / 2))
        divs.append(f'<div style="position:absolute;left:{left}px;top:{gt}px;width:{w}px;height:{h}px;background:{color}"></div>')
    return "".join(divs)


def boxes_from_text(c: Content, color: str) -> tuple[str, np.ndarray]:
    """Per-glyph filled rectangles at the glyph's ink bbox (extent-matched, ink ~2-3x text)."""
    divs, mask = [], np.zeros_like(c.ink)
    for (l, t, r, b), ch in zip(c.chars, c.string):
        if ch.isspace():
            continue
        L, T, Rr, B = int(math.floor(l)), int(math.floor(t)), int(math.ceil(r)), int(math.ceil(b))
        sub = c.ink[T:B, L:Rr]
        if not sub.any():
            continue
        rows = np.nonzero(sub.any(axis=1))[0]; cols = np.nonzero(sub.any(axis=0))[0]
        gl, gr, gt, gb = L + int(cols.min()), L + int(cols.max()), T + int(rows.min()), T + int(rows.max())
        divs.append(f'<div style="position:absolute;left:{gl}px;top:{gt}px;width:{gr - gl + 1}px;height:{gb - gt + 1}px;background:{color}"></div>')
        mask[gt:gb + 1, gl:gr + 1] = True
    return "".join(divs), mask


def bar_from_text(c: Content, seed: Seed) -> tuple[str, np.ndarray]:
    l, t, r, b = c.bbox
    cap = int(round(0.7 * seed.fs))
    base = int(round(c.baseline))
    top = base - cap
    mask = np.zeros_like(c.ink)
    mask[top:base, l:r + 1] = True
    return f'<div style="position:absolute;left:{l}px;top:{top}px;width:{r - l + 1}px;height:{cap}px;background:{seed.text}"></div>', mask


def strip_marks(s: str) -> str:
    return "".join(ch for ch in s if ch not in THAI_MARKS)
