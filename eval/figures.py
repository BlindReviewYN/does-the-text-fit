"""Paper figures -> paper/figures/*.png and *.pdf

    python eval/figures.py

Data: run `core` (rep 0 primary, all reps for flip rates and McNemar), `paraphrase`, `resolution`.
Conventions: reasoning OFF unless stated; Wilson 95 % CIs; cell 11 excluded from pooled panels.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from scipy.stats import binomtest, norm  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from analyze import CELL_ORDER, POOL_EXCLUDE, dprime, wilson  # noqa: E402
from analyze_extra import load_run  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

SLOTS = ["gemini38", "glm53flash", "gpt56sol", "qwen38", "gpt56luna", "dsv4"]
NAME = {"gemini38": "Gemini 3.8 Flash", "glm53flash": "GLM-5.3-Flash", "gpt56sol": "GPT-5.6 Sol",
        "qwen38": "Qwen 3.8 Flash", "gpt56luna": "GPT-5.6 Luna", "dsv4": "DeepSeek V4 Flash"}
COLOR = {"gemini38": "#009E73", "glm53flash": "#D55E00", "gpt56sol": "#0072B2",
         "qwen38": "#CC79A7", "gpt56luna": "#56B4E9", "dsv4": "#E69F00"}
MARK = {"gemini38": "o", "glm53flash": "s", "gpt56sol": "D", "qwen38": "^", "gpt56luna": "v", "dsv4": "P"}
CELL_NAME = {"c01_base": "1 Base text", "c02_bar": "2 Solid bar", "c03_matched": "3 Matched bar", "c04_gibberish": "4 Gibberish",
             "c05_wordgap": "5 Word-gap", "c06_decoy": "6 Decoy (all no)", "c07_pill": "7 Pill", "c08_fill": "8 Fill boundary",
             "c09_bottom": "9 Bottom spill", "c10_thai": "10 Thai", "c11_marks": "11 Thai marks", "c12_thaiwrap": "12 Thai wrap"}
PX_CELLS = ["c01_base", "c02_bar", "c03_matched", "c04_gibberish", "c08_fill", "c09_bottom", "c10_thai", "c12_thaiwrap"]
LEVELS = ["anchor", "m10", "m3", "p4", "p12", "p30"]
LEVEL_LAB = {"anchor": "fit", "m10": "−10", "m3": "−3", "p4": "+4", "p12": "+12", "p30": "+30",
             "m1": "−1", "p3": "+3", "p6": "+6", "p9": "+9", "corner": "corner", "short": "short", "medium": "medium", "long": "long"}

plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "figure.dpi": 150, "savefig.dpi": 300,
                     "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


def rate_ci(k, n):
    lo, hi = wilson(k, n)
    p = k / n if n else np.nan
    return p, p - lo, hi - p


def legend_handles(slots=SLOTS):
    return [Line2D([0], [0], color=COLOR[s], marker=MARK[s], ms=4, lw=1.2, label=NAME[s]) for s in slots]


import json  # noqa: E402
from pathlib import PureWindowsPath  # noqa: E402
_man = pd.DataFrame([json.loads(l) for l in (ROOT / "gen" / "out" / "v1" / "manifest.jsonl").open(encoding="utf-8")])
_man["item"] = _man["path"].map(lambda p: PureWindowsPath(p).stem)
core = load_run("core").merge(_man[["item", "sub_resolution"]], on="item", how="left")
core = core[core["prompt"] == "main"]
r0 = core[core["rep"] == 0]
off = r0[r0["setting"] == "off"]
on = r0[r0["setting"] == "on"]


# ----------------------------------------------------------------------------- F1 level curves
def fig_levels():
    fig, axes = plt.subplots(2, 4, figsize=(7.2, 3.9), sharey=True)
    for ax, cell in zip(axes.flat, PX_CELLS):
        d = off[(off["cell"] == cell) & off["scored"] & (~off["sub_resolution"].astype(bool))]
        x = np.arange(len(LEVELS))
        for i, s in enumerate(SLOTS):
            g = d[d["slot"] == s]
            ys, lo, hi = [], [], []
            for lv in LEVELS:
                gg = g[g["level"] == lv]
                p, a, b = rate_ci(int(gg["said_yes"].sum()), len(gg))
                ys.append(p), lo.append(a), hi.append(b)
            ax.errorbar(x + (i - 2.5) * 0.06, ys, yerr=[lo, hi], color=COLOR[s], marker=MARK[s], ms=3, lw=1, capsize=1.5, elinewidth=0.6)
        ax.axvspan(-0.5, 2.5, color="#f2f2f2", zorder=0)
        ax.axhline(0.5, color="grey", lw=0.4, ls=":")
        ax.set_xticks(x)
        ax.set_xticklabels([LEVEL_LAB[l] for l in LEVELS])
        ax.set_title(CELL_NAME[cell])
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlim(-0.5, len(LEVELS) - 0.5)
    for ax in axes[1]:
        ax.set_xlabel("overflow (px); shaded = fits")
    for ax in axes[:, 0]:
        ax.set_ylabel("P(\"yes\")")
    fig.legend(handles=legend_handles(), loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.03), frameon=False)
    fig.tight_layout()
    save(fig, "fig_levels")


# ----------------------------------------------------------------------------- F2 SDT scatter
def fig_sdt():
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    fa = np.linspace(0.002, 0.6, 200)
    for dp in (1, 2, 3, 4):
        ax.plot(fa, norm.cdf(norm.ppf(fa) + dp), color="#cccccc", lw=0.6, zorder=0)
        xx = {1: 0.55, 2: 0.42, 3: 0.24, 4: 0.09}[dp]
        ax.text(xx, norm.cdf(norm.ppf(xx) + dp) + 0.012, f"d′={dp}", color="#999999", fontsize=6, ha="center")
    for s in SLOTS:
        pts = {}
        for setting, d in (("off", off), ("on", on)):
            g = d[(d["slot"] == s) & d["scored"] & (~d["cell"].isin(POOL_EXCLUDE))]
            if len(g) == 0:
                continue
            pos, neg = g[g["label"] == "yes"], g[g["label"] == "no"]
            pts[setting] = (neg["said_yes"].mean(), pos["said_yes"].mean())
        if "off" in pts:
            ax.plot(*pts["off"], marker=MARK[s], color=COLOR[s], ms=7, ls="none", mec="black", mew=0.4, label=NAME[s])
        if "on" in pts and "off" in pts:
            ax.annotate("", xy=pts["on"], xytext=pts["off"], arrowprops=dict(arrowstyle="->", color=COLOR[s], lw=1))
            ax.plot(*pts["on"], marker=MARK[s], color="white", mec=COLOR[s], mew=1.2, ms=6, ls="none")
    ax.set_xlabel("false-alarm rate (says \"yes\" on fitting text)")
    ax.set_ylabel("hit rate (says \"yes\" on overflow)")
    ax.set_xlim(-0.01, 0.6)
    ax.set_ylim(0.35, 1.02)
    ax.legend(loc="lower right", frameon=False)
    ax.text(0.59, 0.36, "filled = reasoning off, open = on", fontsize=6, color="#555555", ha="right", va="bottom")
    save(fig, "fig_sdt")


# ----------------------------------------------------------------------------- F3 decoy
def fig_decoy():
    d = off[(off["cell"] == "c06_decoy") & off["scored"]].copy()
    d["phrase"] = d["level"].str.split("_").str[0]
    d["gap"] = d["level"].str.split("_").str[1]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), gridspec_kw={"width_ratios": [1.15, 1]})
    x = np.arange(len(SLOTS))
    w = 0.38
    for j, (ph, col) in enumerate((("complete", "#bbbbbb"), ("incomplete", "#444444"))):
        ys, lo, hi = [], [], []
        for s in SLOTS:
            g = d[(d["slot"] == s) & (d["phrase"] == ph)]
            p, a, b = rate_ci(int(g["said_yes"].sum()), len(g))
            ys.append(p), lo.append(a), hi.append(b)
        axes[0].bar(x + (j - 0.5) * w, ys, w, yerr=[lo, hi], color=col, capsize=2, error_kw={"lw": 0.6},
                    label=f"in-box phrase {ph}")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([NAME[s].replace(" ", "\n", 1) for s in SLOTS], fontsize=6.5)
    axes[0].set_ylabel("false-alarm rate on decoys")
    axes[0].set_ylim(0, 1)
    axes[0].legend(frameon=False, loc="upper left")
    axes[0].set_title("Decoy false alarms by phrase completeness (gap pooled)")
    gaps = ["gTwin", "g12", "g30"]
    for s in SLOTS:
        ys, lo, hi = [], [], []
        for gp in gaps:
            g = d[(d["slot"] == s) & (d["gap"] == gp)]
            p, a, b = rate_ci(int(g["said_yes"].sum()), len(g))
            ys.append(p), lo.append(a), hi.append(b)
        axes[1].errorbar(range(3), ys, yerr=[lo, hi], color=COLOR[s], marker=MARK[s], ms=3.5, lw=1, capsize=1.5, elinewidth=0.6, label=NAME[s])
    axes[1].set_xticks(range(3))
    axes[1].set_xticklabels(["4 px (twin)", "12 px", "30 px"])
    axes[1].set_xlabel("gap between box and control")
    axes[1].set_ylim(0, 1)
    axes[1].set_title("by gap (phrase pooled)")
    axes[1].legend(frameon=False, ncol=2, fontsize=6)
    fig.tight_layout()
    save(fig, "fig_decoy")


# ----------------------------------------------------------------------------- F4 reasoning
def fig_reasoning():
    pairs = ["gemini38", "glm53flash", "qwen38", "dsv4"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), gridspec_kw={"width_ratios": [1, 1.6]})
    d = r0[r0["scored"] & (~r0["cell"].isin(POOL_EXCLUDE))]   # repeat 0 only: repeats of one image are not independent pairs
    for i, s in enumerate(pairs):
        piv = d[d["slot"] == s].pivot_table(index=["item", "rep"], columns="setting", values="correct", aggfunc="first").dropna()
        a_off, a_on = piv["off"].mean(), piv["on"].mean()
        b = int(((piv["off"] == 1) & (piv["on"] == 0)).sum())
        c = int(((piv["off"] == 0) & (piv["on"] == 1)).sum())
        p = binomtest(c, b + c, 0.5).pvalue if b + c else np.nan
        axes[0].plot([a_off, a_on], [i, i], color=COLOR[s], lw=2)
        axes[0].plot(a_off, i, marker=MARK[s], color=COLOR[s], ms=6, mec="black", mew=0.4)
        axes[0].plot(a_on, i, marker=MARK[s], color="white", mec=COLOR[s], mew=1.2, ms=6)
        lab = "p < 0.001" if p < 0.001 else f"p = {p:.2f}"
        axes[0].text(max(a_off, a_on) + 0.012, i, f"{100*(a_on-a_off):+.1f} pp, {lab}", va="center", fontsize=6.5)
    axes[0].set_yticks(range(len(pairs)))
    axes[0].set_yticklabels([NAME[s] for s in pairs])
    axes[0].set_xlim(0.7, 1.05)
    axes[0].set_xlabel("accuracy (repeat 0, 11 cells)")
    axes[0].set_title("filled = off, open = on; McNemar")
    axes[0].invert_yaxis()
    # per-cell delta heatmap
    cells = [c for c in CELL_ORDER]
    mat = np.full((len(pairs), len(cells)), np.nan)
    for i, s in enumerate(pairs):
        for j, c in enumerate(cells):
            g = r0[(r0["slot"] == s) & (r0["cell"] == c) & r0["scored"]]
            a0 = g[g["setting"] == "off"]["correct"].mean()
            a1 = g[g["setting"] == "on"]["correct"].mean()
            mat[i, j] = 100 * (a1 - a0)
    im = axes[1].imshow(mat, cmap="RdBu", vmin=-30, vmax=30, aspect="auto")
    axes[1].set_xticks(range(len(cells)))
    axes[1].set_xticklabels([c.split("_")[0][1:].lstrip("0") for c in cells])
    axes[1].set_yticks(range(len(pairs)))
    axes[1].set_yticklabels([NAME[s] for s in pairs])
    axes[1].set_xlabel("cell")
    axes[1].set_title("accuracy change, reasoning on − off (pp, rep 0)")
    for i in range(len(pairs)):
        for j in range(len(cells)):
            axes[1].text(j, i, f"{mat[i, j]:+.0f}", ha="center", va="center", fontsize=6, color="black")
    fig.colorbar(im, ax=axes[1], fraction=0.03, pad=0.02)
    fig.tight_layout()
    save(fig, "fig_reasoning")


# ----------------------------------------------------------------------------- F5 resolution
def fig_resolution():
    res = load_run("resolution")
    res = res[(res["prompt"] == "main") & res["scored"]]
    cells = CELL_ORDER
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), sharey=True)
    for ax, s in zip(axes, ["gpt56sol", "gemini38"]):
        for j, c in enumerate(cells):
            g = res[(res["slot"] == s) & (res["cell"] == c)]
            lo_ = g[g["setting"] == "off_low"]["correct"].mean()
            hi_ = g[g["setting"] == "off_high"]["correct"].mean()
            ax.plot([lo_, hi_], [j, j], color=COLOR[s], lw=1.5)
            ax.plot(lo_, j, marker="o", color="white", mec=COLOR[s], mew=1.2, ms=5)
            ax.plot(hi_, j, marker="o", color=COLOR[s], ms=5, mec="black", mew=0.4)
        ax.set_yticks(range(len(cells)))
        ax.set_yticklabels([CELL_NAME[c] for c in cells])
        ax.invert_yaxis()
        ax.set_xlim(0.3, 1.02)
        ax.set_xlabel("accuracy (25 items per cell)")
        tok = {"gpt56sol": "detail low (218 tok) → high (794 tok)", "gemini38": "media_resolution low (295 tok) → high (1114 tok)"}
        ax.set_title(f"{NAME[s]}: {tok[s]}")
        ax.axvline(0.5, color="grey", lw=0.4, ls=":")
    axes[0].text(0.32, 11.6, "open = low resolution, filled = high", fontsize=6.5, color="#555555")
    fig.tight_layout()
    save(fig, "fig_resolution")


# ----------------------------------------------------------------------------- F6 script
def fig_script():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), gridspec_kw={"width_ratios": [1.2, 1]})
    cells = ["c01_base", "c05_wordgap", "c10_thai", "c12_thaiwrap"]
    x = np.arange(len(cells))
    for i, s in enumerate(SLOTS):
        ys, lo, hi = [], [], []
        for c in cells:
            g = off[(off["slot"] == s) & (off["cell"] == c) & off["scored"] & (off["label"] == "yes")]
            p, a, b = rate_ci(int(g["said_yes"].sum()), len(g))
            ys.append(p), lo.append(a), hi.append(b)
        axes[0].errorbar(x + (i - 2.5) * 0.09, ys, yerr=[lo, hi], color=COLOR[s], marker=MARK[s], ms=3.5, lw=0, capsize=1.5,
                         elinewidth=0.6, label=NAME[s])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["1 EN base\n(mid-word spill)", "5 EN word-gap\n(word spills)", "10 Thai\n(no spaces)", "12 Thai wrap\n(paragraph)"])
    axes[0].set_ylabel("hit rate")
    axes[0].set_ylim(0, 1.03)
    axes[0].set_title("Hit rate by script and structure")
    axes[0].legend(frameon=False, ncol=2, fontsize=6, loc="lower left")
    lv = ["anchor", "m3", "m1", "p3", "p6", "p9"]
    for i, s in enumerate(SLOTS):
        ys, lo, hi = [], [], []
        for l in lv:
            g = off[(off["slot"] == s) & (off["cell"] == "c11_marks") & (off["level"] == l) & off["scored"]]
            p, a, b = rate_ci(int(g["said_yes"].sum()), len(g))
            ys.append(p), lo.append(a), hi.append(b)
        axes[1].errorbar(np.arange(len(lv)) + (i - 2.5) * 0.06, ys, yerr=[lo, hi], color=COLOR[s], marker=MARK[s], ms=3, lw=1,
                         capsize=1.5, elinewidth=0.6)
    axes[1].axvspan(-0.5, 2.5, color="#f2f2f2", zorder=0)
    axes[1].set_xticks(range(len(lv)))
    axes[1].set_xticklabels([LEVEL_LAB[l] for l in lv])
    axes[1].set_xlabel("mark protrusion (px); shaded = inside the edge")
    axes[1].set_ylabel("P(\"yes\")")
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].set_title("11 Thai marks (reported separately)")
    fig.tight_layout()
    save(fig, "fig_script")


# ----------------------------------------------------------------------------- F7 heatmap
def fig_heatmap():
    cells = CELL_ORDER
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw={"width_ratios": [1, 1]})
    for ax, (val, title, vmin, vmax, cmap) in zip(axes, [("acc", "accuracy", 0.4, 1.0, "viridis"), ("dp", "d′ (cell 6: FA shown)", 0, 4.6, "magma")]):
        mat = np.full((len(cells), len(SLOTS)), np.nan)
        txt = np.full((len(cells), len(SLOTS)), "", dtype=object)
        for j, s in enumerate(SLOTS):
            for i, c in enumerate(cells):
                g = off[(off["slot"] == s) & (off["cell"] == c) & off["scored"]]
                if val == "acc":
                    mat[i, j] = g["correct"].mean()
                    txt[i, j] = f"{mat[i, j]:.2f}"
                else:
                    pos, neg = g[g["label"] == "yes"], g[g["label"] == "no"]
                    if len(pos) == 0:
                        mat[i, j] = np.nan
                        txt[i, j] = f"FA {neg['said_yes'].mean():.2f}"
                    else:
                        dp, _ = dprime(int(pos["said_yes"].sum()), len(pos), int(neg["said_yes"].sum()), len(neg))
                        mat[i, j] = dp
                        txt[i, j] = f"{dp:.1f}"
        im = ax.imshow(mat, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
        for i in range(len(cells)):
            for j in range(len(SLOTS)):
                v = mat[i, j]
                col = "white" if (np.isnan(v) or (v - vmin) / (vmax - vmin) < 0.55) else "black"
                ax.text(j, i, txt[i, j], ha="center", va="center", fontsize=6, color=col)
        ax.set_xticks(range(len(SLOTS)))
        ax.set_xticklabels([NAME[s].replace(" ", "\n", 1) for s in SLOTS], fontsize=6)
        ax.set_yticks(range(len(cells)))
        ax.set_yticklabels([CELL_NAME[c] for c in cells], fontsize=6.5)
        ax.set_title(title + " (reasoning off, rep 0)")
        fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    fig.tight_layout()
    save(fig, "fig_heatmap")


# ----------------------------------------------------------------------------- F8 polarity
def fig_polarity():
    para = load_run("paraphrase")
    para = para[para["scored"] & (para["setting"] == "off")]
    items = set(para["item"])
    base = off[off["item"].isin(items) & off["scored"]]
    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    for s in SLOTS:
        pts = {}
        for name, d in (("main", base[base["slot"] == s]), ("para2", para[(para["slot"] == s) & (para["prompt"] == "para2")])):
            d = d[~d["cell"].isin(POOL_EXCLUDE)]
            pos, neg = d[d["label"] == "yes"], d[d["label"] == "no"]
            pts[name] = (neg["said_yes"].mean(), pos["said_yes"].mean())
        ax.plot(*pts["main"], marker=MARK[s], color=COLOR[s], ms=7, ls="none", mec="black", mew=0.4, label=NAME[s])
        ax.annotate("", xy=pts["para2"], xytext=pts["main"], arrowprops=dict(arrowstyle="->", color=COLOR[s], lw=1))
        ax.plot(*pts["para2"], marker=MARK[s], color="white", mec=COLOR[s], mew=1.2, ms=6, ls="none")
    fa = np.linspace(0.002, 0.5, 200)
    for dp in (1, 2, 3, 4):
        ax.plot(fa, norm.cdf(norm.ppf(fa) + dp), color="#cccccc", lw=0.6, zorder=0)
    ax.set_xlabel("false-alarm rate")
    ax.set_ylabel("hit rate")
    ax.set_xlim(-0.01, 0.4)
    ax.set_ylim(0.35, 1.02)
    ax.set_title("Prompt polarity: \"extends beyond?\" (filled)\n→ \"fully contained?\" (open, inverted)", fontsize=8)
    ax.legend(loc="lower right", frameon=False)
    save(fig, "fig_polarity")


# ----------------------------------------------------------------------------- F9 shape
def fig_shape():
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    conds = [("c01_base", "p4", "rect +4"), ("c01_base", "p12", "rect +12"), ("c08_fill", "p4", "fill +4"), ("c08_fill", "p12", "fill +12"),
             ("c07_pill", "corner", "pill corner"), ("c07_pill", "p4", "pill +4"), ("c07_pill", "p12", "pill +12")]
    x = np.arange(len(conds))
    for i, s in enumerate(SLOTS):
        ys, lo, hi = [], [], []
        for c, l, _ in conds:
            g = off[(off["slot"] == s) & (off["cell"] == c) & (off["level"] == l) & off["scored"]]
            p, a, b = rate_ci(int(g["said_yes"].sum()), len(g))
            ys.append(p), lo.append(a), hi.append(b)
        ax.errorbar(x + (i - 2.5) * 0.09, ys, yerr=[lo, hi], color=COLOR[s], marker=MARK[s], ms=3.5, lw=0, capsize=1.5, elinewidth=0.6, label=NAME[s])
    ax.set_xticks(x)
    ax.set_xticklabels([c[2] for c in conds], rotation=30, ha="right")
    ax.set_ylabel("hit rate")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("Boundary type: border vs fill-only vs capsule")
    ax.legend(frameon=False, ncol=3, fontsize=6, loc="upper center", bbox_to_anchor=(0.5, -0.35))
    save(fig, "fig_shape")


# ----------------------------------------------------------------------------- F10 flips
def fig_flips():
    d = core[core["scored"] & (~core["cell"].isin(POOL_EXCLUDE))]
    g = d.groupby(["slot", "setting", "item"])["said_yes"].agg(["sum", "size"]).reset_index()
    g = g[g["size"] > 1]
    g["flip"] = (g["sum"] > 0) & (g["sum"] < g["size"])
    fr = g.groupby(["slot", "setting"])["flip"].mean().unstack()
    fig, ax = plt.subplots(figsize=(3.6, 2.4))
    x = np.arange(len(SLOTS))
    for j, setting in enumerate(["off", "on"]):
        ys = [fr.loc[s, setting] if (s in fr.index and setting in fr.columns and not np.isnan(fr.loc[s, setting])) else 0 for s in SLOTS]
        ax.bar(x + (j - 0.5) * 0.38, ys, 0.38, color=[COLOR[s] for s in SLOTS], alpha=1.0 if setting == "off" else 0.45,
               edgecolor="black", lw=0.3, label=f"reasoning {setting}")
    ax.set_xticks(x)
    ax.set_xticklabels([NAME[s].replace(" ", "\n", 1) for s in SLOTS], fontsize=6)
    ax.set_ylabel("share of items whose 3 repeats disagree")
    ax.set_title("Self-consistency at temperature 0")
    ax.legend(frameon=False)
    save(fig, "fig_flips")


def main_figures():
    fig_levels()
    fig_sdt()
    fig_decoy()
    fig_reasoning()
    fig_resolution()
    fig_script()
    fig_heatmap()
    fig_polarity()
    fig_shape()
    fig_flips()


# ----------------------------------------------------------------------------- F0 stimuli
def fig_stimuli():
    """One crop per cell (a positive level where the cell has one), 2x scale, with the cell name and level."""
    from PIL import Image, ImageDraw, ImageFont
    picks = [("c01_base", "p4", "en02"), ("c02_bar", "p4", "en02"), ("c03_matched", "p4", "en02"), ("c04_gibberish", "p4", "en02"),
             ("c05_wordgap", "short", "en02"), ("c06_decoy", "incomplete_gTwin", "en02"), ("c07_pill", "corner", "pill02"),
             ("c08_fill", "p4", "en02"), ("c09_bottom", "p4", "para02"), ("c10_thai", "p4", "th02"), ("c11_marks", "p6", "thm02"),
             ("c12_thaiwrap", "p4", "thp02")]
    LAB = {"p4": "+4 px", "p6": "+6 px", "short": "short word spills", "incomplete_gTwin": "control 4 px away (fits)", "corner": "corner-cross"}
    man = {r["item"]: r for r in _man.to_dict("records")}
    tiles = []
    for cell, level, sid in picks:
        item = f"{cell}_{level}_{sid}"
        r = man[item]
        bx, by, bw, bh = r["geo"]
        ix0, iy0, ix1, iy1 = r["ink_bbox"]
        x0, y0 = min(bx, ix0) - 14, min(by, iy0) - 14
        x1, y1 = max(bx + bw, ix1) + 14, max(by + bh, iy1) + 14
        im = Image.open(ROOT / "gen" / "out" / "v1" / f"{item}.png").convert("RGB").crop((x0, y0, x1, y1))
        im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
        tiles.append((im, f"{CELL_NAME[cell]} — {LAB.get(level, level)}"))
    W = max(t[0].width for t in tiles)
    cols, pad, cap = 3, 16, 26
    rows_ = (len(tiles) + cols - 1) // cols
    H = max(t[0].height for t in tiles)
    sheet = Image.new("RGB", (cols * (W + pad) + pad, rows_ * (H + cap + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(str(ROOT / "gen" / "fonts" / "Inter.ttf"), 20)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    for k, (im, label) in enumerate(tiles):
        cx, cy = pad + (k % cols) * (W + pad), pad + (k // cols) * (H + cap + pad)
        sheet.paste(im, (cx, cy + cap))
        draw.text((cx, cy), label, fill="#222222", font=font)
    sheet.save(OUT / "fig_stimuli.png")
    print("saved fig_stimuli")




# ----------------------------------------------------------------------------- F0b Thai marks examples
def fig_thai_marks():
    """Rows = mark family (single above, stacked above, tall consonant, below); columns = fit / -1 / +3 / +6 px.
    At +3 only the mark crosses the edge; the consonant body stays inside."""
    from PIL import Image, ImageDraw, ImageFont
    man = [r for r in _man.to_dict("records") if r["cell"] == "c11_marks"]
    fams = [("single", "single mark above (tone / vowel)"), ("stacked", "stacked marks above (vowel + tone)"),
            ("tall", "tall consonant (ป ฝ ฟ)"), ("below", "mark below (vowel ุ ู)")]
    levels = [("anchor", "fits"), ("m1", "1 px inside"), ("p3", "+3 px"), ("p6", "+6 px")]
    font = ImageFont.truetype(str(ROOT / "gen" / "fonts" / "Sarabun.ttf"), 26)
    tiles = {}
    for fam, _ in fams:
        sids = sorted({r["sid"] for r in man if r["family"] == fam})
        sid = sids[1] if len(sids) > 1 else sids[0]
        for lv, _ in levels:
            r = next(x for x in man if x["family"] == fam and x["level"] == lv and x["sid"] == sid)
            bx, by, bw, bh = r["geo"]
            x0, y0, x1, y1 = bx - 12, by - 22, bx + bw + 12, by + bh + 22     # one window per box: columns align
            im = Image.open(ROOT / "gen" / "out" / "v1" / f"{r['item']}.png").convert("RGB").crop((x0, y0, x1, y1))
            tiles[(fam, lv)] = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
    W = max(t.width for t in tiles.values())
    H = max(t.height for t in tiles.values())
    pad, cap, left = 18, 40, 470
    sheet = Image.new("RGB", (left + 4 * (W + pad) + pad, cap + 4 * (H + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)
    for j, (_, lab) in enumerate(levels):
        draw.text((left + pad + j * (W + pad), 6), lab, fill="#222222", font=font)
    for i, (fam, lab) in enumerate(fams):
        y = cap + pad + i * (H + pad)
        draw.text((10, y + H // 2 - 12), lab, fill="#222222", font=font)
        for j, (lv, _) in enumerate(levels):
            sheet.paste(tiles[(fam, lv)], (left + pad + j * (W + pad), y))
    sheet.save(OUT / "fig_thai_marks.png")
    print("saved fig_thai_marks")


if __name__ == "__main__":
    if "--stimuli" in sys.argv:
        fig_stimuli()
        fig_thai_marks()
    else:
        main_figures()
        fig_stimuli()
        fig_thai_marks()
