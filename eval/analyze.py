"""Analysis of a run: per cell x slot x setting accuracy / hit / FA / d' with CIs,
per-level curves for the px-axis cells, reasoning-pair McNemar tests, repeat consistency.

    python eval/analyze.py core            # writes eval/out/core/analysis/*.md, *.csv, *.png
    python eval/analyze.py core --rep 0    # primary = rep 0 only (default: rep 0 primary, majority secondary)

Conventions (pre-registered in 02-overflow-benchmark-design.md / 04-eval-plan.md):
- primary unit = one call per item (rep 0); majority-of-3 reported as secondary
- unparsed / error answers are counted and excluded from acc/hit/FA (never mapped to a label)
- sub_resolution items excluded from pooled level curves, reported separately
- d' with log-linear correction (add 0.5 hits / 1 trial per cell); criterion c = -(zH + zF)/2
- CIs: Wilson 95% for proportions; McNemar exact (binomial) on discordant pairs
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
from parse import PARSER_VERSION, parse_yes_no  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POOL_EXCLUDE = ["c11_marks"]   # protocol: cell 11 reported separately, never pooled
MANIFEST = ROOT / "gen" / "out" / "v1" / "manifest.jsonl"
PX_CELLS = ["c01_base", "c02_bar", "c03_matched", "c04_gibberish", "c08_fill", "c09_bottom", "c10_thai", "c12_thaiwrap"]
LEVEL_PX = {"anchor": None, "m10": -10, "m3": -3, "m1": -1, "p3": 3, "p4": 4, "p6": 6, "p9": 9, "p12": 12, "p30": 30}
CELL_ORDER = ["c01_base", "c02_bar", "c03_matched", "c04_gibberish", "c05_wordgap", "c06_decoy", "c07_pill", "c08_fill",
              "c09_bottom", "c10_thai", "c11_marks", "c12_thaiwrap"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def dprime(hits, npos, fas, nneg):
    if npos == 0 or nneg == 0:
        return float("nan"), float("nan")
    h = (hits + 0.5) / (npos + 1)
    f = (fas + 0.5) / (nneg + 1)
    zh, zf = norm.ppf(h), norm.ppf(f)
    return zh - zf, -(zh + zf) / 2


def load(run):
    rows = {}
    for line in (ROOT / "eval" / "out" / run / "responses.jsonl").open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows[r["key"]] = r
    df = pd.DataFrame(rows.values())
    # re-parse from stored text with the current parser (stored `answer` may be from an older parser)
    df["answer"] = [("error" if e else parse_yes_no(t)) for e, t in zip(df["error"], df["text"])]
    df["parser"] = PARSER_VERSION
    man = pd.DataFrame([json.loads(l) for l in MANIFEST.open(encoding="utf-8")])
    man["item"] = man["path"].map(lambda p: PureWindowsPath(p).stem)
    df = df.merge(man[["item", "sub_resolution", "p", "family", "pool"]], on="item", how="left")
    df["reasoning_tokens"] = df["usage"].map(lambda u: (u or {}).get("reasoning") or 0)
    df["out_tokens"] = df["usage"].map(lambda u: (u or {}).get("out") or 0)
    df["scored"] = df["answer"].isin(["yes", "no"])
    df["correct"] = (df["answer"] == df["label"]) & df["scored"]
    df["said_yes"] = df["answer"] == "yes"
    return df


def majority(df):
    """Collapse repeats to one row per (item, slot, setting): majority answer, tie -> 'tie'."""
    g = df[df["scored"]].groupby(["item", "slot", "setting", "prompt"])
    out = g.agg(n=("answer", "size"), ny=("said_yes", "sum"), label=("label", "first"), cell=("cell", "first"),
                level=("level", "first"), sub_resolution=("sub_resolution", "first")).reset_index()
    out["answer"] = np.where(out["ny"] * 2 > out["n"], "yes", np.where(out["ny"] * 2 < out["n"], "no", "tie"))
    out["flip"] = (out["ny"] > 0) & (out["ny"] < out["n"])
    out["scored"] = out["answer"].isin(["yes", "no"])
    out["correct"] = (out["answer"] == out["label"]) & out["scored"]
    out["said_yes"] = out["answer"] == "yes"
    return out


def table(df, by):
    recs = []
    for keys, g in df.groupby(by):
        keys = keys if isinstance(keys, tuple) else (keys,)
        s = g[g["scored"]]
        pos, neg = s[s["label"] == "yes"], s[s["label"] == "no"]
        k = int(s["correct"].sum())
        n = len(s)
        h, f = int(pos["said_yes"].sum()), int(neg["said_yes"].sum())
        dp, c = dprime(h, len(pos), f, len(neg))
        lo, hi = wilson(k, n)
        rec = dict(zip(by, keys))
        rec.update(n=len(g), scored=n, unscored=len(g) - n, acc=k / n if n else float("nan"), acc_lo=lo, acc_hi=hi,
                   hit=h / len(pos) if len(pos) else float("nan"), npos=len(pos),
                   fa=f / len(neg) if len(neg) else float("nan"), nneg=len(neg), dprime=dp, criterion=c,
                   reasoning_tokens=g["reasoning_tokens"].mean() if "reasoning_tokens" in g else float("nan"))
        recs.append(rec)
    return pd.DataFrame(recs)


def mcnemar_pairs(df, slots):
    """Reasoning on vs off on identical items (same rep), per slot and per cell."""
    recs = []
    for slot in slots:
        d = df[(df["slot"] == slot) & df["scored"]]
        if set(d["setting"]) < {"off", "on"}:
            continue
        piv = d.pivot_table(index=["item", "rep", "cell"], columns="setting", values="correct", aggfunc="first").dropna()
        cells_of = piv.index.get_level_values("cell")
        for scope, sub in [("all", piv[~cells_of.isin(POOL_EXCLUDE)])] + [(c, piv[cells_of == c]) for c in CELL_ORDER]:
            if len(sub) == 0:
                continue
            b = int(((sub["off"] == 1) & (sub["on"] == 0)).sum())  # off right, on wrong
            c_ = int(((sub["off"] == 0) & (sub["on"] == 1)).sum())  # on right, off wrong
            p = binomtest(c_, b + c_, 0.5).pvalue if b + c_ > 0 else float("nan")
            recs.append(dict(slot=slot, cell=scope, n=len(sub), acc_off=sub["off"].mean(), acc_on=sub["on"].mean(),
                             on_gains=c_, on_loses=b, p_mcnemar=p))
    return pd.DataFrame(recs)


def level_curves(df):
    """Per slot x setting x cell x level: P(yes) with Wilson CI, px-axis cells only, sub_resolution excluded."""
    d = df[df["cell"].isin(PX_CELLS) & df["scored"] & (~df["sub_resolution"].astype(bool))]
    recs = []
    for (slot, setting, cell, level), g in d.groupby(["slot", "setting", "cell", "level"]):
        k, n = int(g["said_yes"].sum()), len(g)
        lo, hi = wilson(k, n)
        recs.append(dict(slot=slot, setting=setting, cell=cell, level=level, px=LEVEL_PX.get(level), n=n,
                         p_yes=k / n, lo=lo, hi=hi, label=g["label"].iloc[0]))
    return pd.DataFrame(recs)


def plot_curves(curves, out_dir, tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cells = [c for c in PX_CELLS if c in set(curves["cell"])]
    if not cells:
        return
    fig, axes = plt.subplots(2, 4, figsize=(16, 7), sharey=True)
    order = ["anchor", "m10", "m3", "m1", "p3", "p4", "p6", "p9", "p12", "p30"]
    for ax, cell in zip(axes.flat, cells):
        d = curves[curves["cell"] == cell]
        lv = [l for l in order if l in set(d["level"])]
        x = np.arange(len(lv))
        for (slot, setting), g in d.groupby(["slot", "setting"]):
            g = g.set_index("level").reindex(lv)
            ls = "-" if setting == "on" else "--"
            py, lo, hi = g["p_yes"].to_numpy(float), g["lo"].to_numpy(float), g["hi"].to_numpy(float)
            ax.errorbar(x, py, yerr=[py - lo, hi - py], fmt="o" + ls, ms=3,
                        capsize=2, lw=1, label=f"{slot}/{setting}")
        ax.set_xticks(x)
        ax.set_xticklabels(lv, fontsize=8)
        ax.set_title(cell, fontsize=10)
        ax.axhline(0.5, color="grey", lw=0.5)
        ax.set_ylim(-0.02, 1.02)
    for ax in axes.flat[len(cells):]:
        ax.axis("off")
    axes.flat[0].set_ylabel("P(yes)")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", fontsize=8, ncol=min(10, len(labels)), bbox_to_anchor=(0.5, 0.0))
    fig.suptitle(f"P(yes) by level, px-axis cells ({tag}); dashed = reasoning off, solid = on; sub-resolution items excluded")
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out_dir / f"level_curves_{tag}.png", dpi=130)
    plt.close(fig)


def heatmap(tab, out_dir, tag, value="acc"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tab = tab.copy()
    tab["col"] = tab["slot"] + "/" + tab["setting"]
    piv = tab.pivot_table(index="cell", columns="col", values=value).reindex(CELL_ORDER)
    fig, ax = plt.subplots(figsize=(1.1 * len(piv.columns) + 3, 6))
    im = ax.imshow(piv.values.astype(float), vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels(piv.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(piv.index)))
    ax.set_yticklabels(piv.index, fontsize=8)
    for i in range(len(piv.index)):
        for j in range(len(piv.columns)):
            v = piv.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7, color="w" if v < 0.6 else "k")
    fig.colorbar(im, ax=ax, label=value)
    ax.set_title(f"{value} per cell ({tag})")
    fig.tight_layout()
    fig.savefig(out_dir / f"heatmap_{value}_{tag}.png", dpi=130)
    plt.close(fig)


def md(df, floatfmt=".3f"):
    return df.to_markdown(index=False, floatfmt=floatfmt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--prompt", default="main")
    args = ap.parse_args()
    out_dir = ROOT / "eval" / "out" / args.run / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load(args.run)
    df = df[df["prompt"] == args.prompt]
    slots = sorted(df["slot"].unique())
    parts = [f"# Analysis of run `{args.run}` (prompt `{args.prompt}`)\n",
             f"rows={len(df)} items={df['item'].nunique()} slots={slots} settings={sorted(df['setting'].unique())} "
             f"reps={sorted(df['rep'].unique())}; errors={int((df['answer'] == 'error').sum())} unparsed={int((df['answer'] == 'unparsed').sum())}\n"]

    prim = df[df["rep"] == 0]
    pooled = prim[~prim["cell"].isin(POOL_EXCLUDE)]
    # 1. overall per slot x setting (primary = rep 0), cell 11 excluded from pooling
    t = table(pooled, ["slot", "setting"])
    t.to_csv(out_dir / "overall_rep0.csv", index=False)
    parts.append(f"## Overall per model x setting (rep 0; pooled over cells except {POOL_EXCLUDE})\n\n" + md(t) + "\n")
    # 2. per cell
    tc = table(prim, ["slot", "setting", "cell"])
    tc.to_csv(out_dir / "per_cell_rep0.csv", index=False)
    piv = tc.pivot_table(index="cell", columns=["slot", "setting"], values="acc").reindex(CELL_ORDER)
    piv.columns = [f"{a}/{b}" for a, b in piv.columns]
    parts.append("## Accuracy per cell (rep 0)\n\n" + piv.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")
    pivd = tc.pivot_table(index="cell", columns=["slot", "setting"], values="dprime").reindex(CELL_ORDER)
    pivd.columns = [f"{a}/{b}" for a, b in pivd.columns]
    parts.append("## d' per cell (rep 0; cell 6 has no positives -> NaN, see FA)\n\n" + pivd.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")
    pivf = tc.pivot_table(index="cell", columns=["slot", "setting"], values="fa").reindex(CELL_ORDER)
    pivf.columns = [f"{a}/{b}" for a, b in pivf.columns]
    parts.append("## False-alarm rate per cell (rep 0)\n\n" + pivf.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")
    heatmap(tc, out_dir, "rep0", "acc")
    heatmap(tc, out_dir, "rep0", "dprime")
    # 3. level curves
    cur = level_curves(prim)
    cur.to_csv(out_dir / "level_curves_rep0.csv", index=False)
    plot_curves(cur, out_dir, "rep0")
    # 4. McNemar reasoning pairs (all reps, same rep paired)
    mc = mcnemar_pairs(df, slots)
    if len(mc):
        mc.to_csv(out_dir / "mcnemar_reasoning.csv", index=False)
        parts.append(f"## Reasoning on vs off, McNemar on identical items (all reps; 'all' excludes {POOL_EXCLUDE})\n\n" + md(mc[mc["cell"] == "all"], ".3f") + "\n")
    # 5. majority + consistency
    maj = majority(df)
    if maj["n"].max() > 1:
        majp = maj[~maj["cell"].isin(POOL_EXCLUDE)]
        tm = table(majp.assign(reasoning_tokens=np.nan), ["slot", "setting"])
        flips = majp.groupby(["slot", "setting"])["flip"].mean().reset_index().rename(columns={"flip": "flip_rate"})
        tm = tm.merge(flips, on=["slot", "setting"])
        tm.to_csv(out_dir / "overall_majority.csv", index=False)
        parts.append("## Majority-of-repeats (secondary) and flip rate\n\n" + md(tm) + "\n")
        fc = maj.groupby(["slot", "setting", "cell"])["flip"].mean().reset_index()
        pf = fc.pivot_table(index="cell", columns=["slot", "setting"], values="flip").reindex(CELL_ORDER)
        pf.columns = [f"{a}/{b}" for a, b in pf.columns]
        parts.append("## Flip rate per cell (share of items whose repeats disagree)\n\n" + pf.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")
    # 6. sub-resolution items
    sr = prim[prim["sub_resolution"].astype(bool)]
    if len(sr):
        parts.append("## Sub-resolution positives (excluded from level curves)\n\n" + md(table(sr, ["slot", "setting"])) + "\n")
    # 7. tokens / latency
    tl = df.groupby(["slot", "setting"]).agg(reasoning_tokens=("reasoning_tokens", "mean"), out_tokens=("out_tokens", "mean"),
                                             latency=("latency", "mean"), n=("key", "size")).reset_index()
    parts.append("## Tokens and latency (all reps)\n\n" + md(tl, ".1f") + "\n")
    (out_dir / "analysis.md").write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts[:3]))
    print("->", out_dir)


if __name__ == "__main__":
    main()
