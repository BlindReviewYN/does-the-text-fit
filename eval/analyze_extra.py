"""Subset analyses: paraphrase robustness, transcription probe (OCR), resolution ablation.

    python eval/analyze_extra.py          # writes eval/out/analysis_extra/analysis_extra.md (+ csv, png)

Inputs: runs `core` (main prompt, rep 0, reasoning off), `paraphrase` (para1, para2),
`ocr` (prompt ocr), `resolution` (settings off_low / off_high). Conventions as in analyze.py:
answers re-parsed from stored text; unparsed excluded from rates and counted; cell 11 never pooled.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).parent))
from analyze import CELL_ORDER, POOL_EXCLUDE, dprime, wilson  # noqa: E402
from parse import parse_yes_no  # noqa: E402
from registry import PROMPT_META  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "out" / "analysis_extra"
MANIFEST = ROOT / "gen" / "out" / "v1" / "manifest.jsonl"
THAI = {"c10_thai", "c11_marks", "c12_thaiwrap"}


def load_run(run):
    rows = {}
    p = ROOT / "eval" / "out" / run / "responses.jsonl"
    if not p.exists():
        return pd.DataFrame()
    for line in p.open(encoding="utf-8"):
        if line.strip():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows[r["key"]] = r
    df = pd.DataFrame(rows.values())
    df["raw"] = [("error" if e else parse_yes_no(t)) for e, t in zip(df["error"], df["text"])]
    pol = df["prompt"].map(lambda p: PROMPT_META.get(p, {}).get("polarity", 1))
    inv = {"yes": "no", "no": "yes"}
    df["answer"] = [inv.get(a, a) if p == -1 else a for a, p in zip(df["raw"], pol)]
    df["scored"] = df["answer"].isin(["yes", "no"])
    df["correct"] = (df["answer"] == df["label"]) & df["scored"]
    df["said_yes"] = df["answer"] == "yes"
    df["raw_yes"] = df["raw"] == "yes"
    return df


def rates(g):
    s = g[g["scored"]]
    pos, neg = s[s["label"] == "yes"], s[s["label"] == "no"]
    h, f = int(pos["said_yes"].sum()), int(neg["said_yes"].sum())
    k, n = int(s["correct"].sum()), len(s)
    lo, hi = wilson(k, n)
    dp, c = dprime(h, len(pos), f, len(neg))
    return dict(n=len(g), scored=n, unscored=len(g) - n, acc=k / n if n else np.nan, acc_lo=lo, acc_hi=hi,
                hit=h / len(pos) if len(pos) else np.nan, fa=f / len(neg) if len(neg) else np.nan,
                dprime=dp, criterion=c, p_raw_yes=g["raw_yes"].mean())


def table(df, by):
    recs = []
    for keys, g in df.groupby(by):
        keys = keys if isinstance(keys, tuple) else (keys,)
        rec = dict(zip(by, keys))
        rec.update(rates(g))
        recs.append(rec)
    return pd.DataFrame(recs)


def mcnemar(a, b):
    """a, b: boolean Series aligned on the same index (correct under condition A / B)."""
    a, b = a.astype(bool), b.astype(bool)
    x = int((a & ~b).sum())
    y = int((~a & b).sum())
    p = binomtest(y, x + y, 0.5).pvalue if x + y else np.nan
    return x, y, p


def md(df, ff=".3f"):
    return df.to_markdown(index=False, floatfmt=ff)


# ----------------------------------------------------------------------------- paraphrase
def paraphrase(parts):
    para = load_run("paraphrase")
    core = load_run("core")
    if para.empty:
        parts.append("## Paraphrase robustness\n\n(no `paraphrase` run yet)\n")
        return
    items = set(para["item"])
    base = core[(core["prompt"] == "main") & (core["setting"] == "off") & (core["rep"] == 0) & core["item"].isin(items)]
    df = pd.concat([base, para[para["setting"] == "off"]], ignore_index=True)
    df = df[~df["cell"].isin(POOL_EXCLUDE)]
    t = table(df, ["slot", "prompt"])
    t["prompt"] = pd.Categorical(t["prompt"], ["main", "para1", "para2"])
    t = t.sort_values(["slot", "prompt"])
    t.to_csv(OUT / "paraphrase_overall.csv", index=False)
    parts.append("## Paraphrase robustness (240 items, reasoning off; para2 polarity-inverted; cell 11 excluded)\n\n"
                 "`p_raw_yes` = share of raw 'yes' answers before inversion: for para2 a high value means the model says the text fits.\n\n"
                 + md(t) + "\n")
    # per-item agreement across the three prompts (same rep 0 / single call each)
    piv = df[df["scored"]].pivot_table(index=["slot", "item", "label"], columns="prompt", values="answer", aggfunc="first")
    piv = piv.dropna()
    prompts = [p for p in ["main", "para1", "para2"] if p in piv.columns]
    recs = []
    for slot, g in piv.groupby(level="slot"):
        lab = g.index.get_level_values("label")
        rec = dict(slot=slot, n=len(g), all_agree=np.mean([len(set(row)) == 1 for row in g[prompts].to_numpy()]))
        for p in prompts:
            rec[f"acc_{p}"] = (g[p] == lab).mean()
        for p in prompts[1:]:
            x, y, pv = mcnemar(g["main"] == lab, g[p] == lab)
            rec[f"p_main_vs_{p}"] = pv
        recs.append(rec)
    a = pd.DataFrame(recs)
    a.to_csv(OUT / "paraphrase_agreement.csv", index=False)
    parts.append("### Per-item agreement across prompts and McNemar (main vs each paraphrase)\n\n" + md(a, ".3f") + "\n")
    # per cell accuracy by prompt
    tc = table(df, ["slot", "prompt", "cell"])
    pv = tc.pivot_table(index="cell", columns=["slot", "prompt"], values="acc").reindex([c for c in CELL_ORDER if c not in POOL_EXCLUDE])
    pv.columns = [f"{a}/{b}" for a, b in pv.columns]
    pv.reset_index().to_csv(OUT / "paraphrase_per_cell.csv", index=False)
    parts.append("### Accuracy per cell by prompt\n\n" + pv.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")


# ----------------------------------------------------------------------------- OCR
def _lev(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _norm(s):
    s = s.replace("​", "")
    s = re.sub(r"\s+", " ", s).strip().strip("\"'“”‘’`*")
    return s


def _candidates(text):
    t = text or ""
    cands = [_norm(t)]
    for q in re.findall(r"[\"“]([^\"”]{3,})[\"”]", t):
        cands.append(_norm(q))
    if ":" in t:
        cands.append(_norm(t.split(":", 1)[1]))
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if lines:
        cands.append(_norm(max(lines, key=len)))
    return [c for c in cands if c]


def cer(text, refs):
    best = np.inf
    for ref in refs:
        ref = _norm(ref)
        if not ref:
            continue
        for c in _candidates(text):
            best = min(best, _lev(c, ref) / len(ref))
    return best if np.isfinite(best) else np.nan


def ocr(parts):
    df = load_run("ocr")
    if df.empty:
        parts.append("## Transcription probe\n\n(no `ocr` run yet)\n")
        return
    man = {}
    for line in MANIFEST.open(encoding="utf-8"):
        r = json.loads(line)
        man[PureWindowsPath(r["path"]).stem] = r
    pools = json.load((ROOT / "gen" / "seeds" / "pools.json").open(encoding="utf-8"))["P1_en_frames"]
    refs = []
    for it in df["item"]:
        r = man[it]
        rs = [r["string"]]
        m = re.search(r"word=([^;]+)", r.get("note") or "")
        if m:
            rs.append(r["string"] + " " + m.group(1))
        # complete-phrase decoys are rendered as frame + medium filler, but the manifest stores the frame only
        if r["cell"] == "c06_decoy" and r["level"].startswith("complete"):
            rs = [r["string"] + " " + pools[r["row"]]["medium"]]
        refs.append(rs)
    df["cer"] = [cer(t, rs) if not e else np.nan for t, rs, e in zip(df["text"], refs, df["error"])]
    df["script"] = np.where(df["cell"].isin(THAI), "TH", "EN")
    df.to_csv(OUT / "ocr_rows.csv", index=False, columns=["item", "cell", "slot", "cer", "text"])
    t = df.groupby(["slot", "script"]).agg(n=("cer", "size"), median_cer=("cer", "median"), mean_cer=("cer", "mean"),
                                           cer_lt_0_1=("cer", lambda x: (x < 0.1).mean()),
                                           cer_lt_0_3=("cer", lambda x: (x < 0.3).mean())).reset_index()
    t.to_csv(OUT / "ocr_by_script.csv", index=False)
    parts.append("## Transcription probe (\"Read the text in the box.\", 30 items x 8 text cells, reasoning off)\n\n"
                 "CER = Levenshtein / reference length, best over plausible extractions of the reply (whole reply, quoted span, "
                 "text after a colon, longest line) and over reference variants (in-box string; plus the spilled word for cell 5).\n\n"
                 + md(t, ".3f") + "\n")
    tc = df.groupby(["slot", "cell"])["cer"].median().reset_index().pivot_table(index="cell", columns="slot", values="cer")
    tc = tc.reindex([c for c in CELL_ORDER if c in set(df["cell"])])
    parts.append("### Median CER per cell\n\n" + tc.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")
    # OCR-conditioned overflow accuracy: same items, core main prompt rep 0 off, split by CER < 0.3
    core = load_run("core")
    base = core[(core["prompt"] == "main") & (core["setting"] == "off") & (core["rep"] == 0)]
    m = df[["item", "slot", "cer", "script"]].merge(base[["item", "slot", "correct", "scored", "label"]], on=["item", "slot"])
    m = m[m["scored"]]
    m["readable"] = m["cer"] < 0.3
    tt = m.groupby(["slot", "script", "readable"]).agg(n=("correct", "size"), acc=("correct", "mean")).reset_index()
    tt.to_csv(OUT / "ocr_conditioned_accuracy.csv", index=False)
    parts.append("### Overflow accuracy (main prompt, rep 0, off) conditioned on transcription success (CER < 0.3)\n\n" + md(tt, ".3f") + "\n")


# ----------------------------------------------------------------------------- resolution
def resolution(parts):
    df = load_run("resolution")
    if df.empty:
        parts.append("## Resolution ablation\n\n(no `resolution` run yet)\n")
        return
    df = df[df["prompt"] == "main"]
    t = table(df[~df["cell"].isin(POOL_EXCLUDE)], ["slot", "setting"])
    t.to_csv(OUT / "resolution_overall.csv", index=False)
    tok = df.groupby(["slot", "setting"]).agg(in_tokens=("usage", lambda u: np.mean([(x or {}).get("in") or 0 for x in u]))).reset_index()
    t = t.merge(tok, on=["slot", "setting"])
    parts.append("## Resolution ablation (300 items, reasoning off; OpenAI `detail`, Gemini `media_resolution`; cell 11 excluded)\n\n" + md(t) + "\n")
    recs = []
    for slot, g in df[df["scored"]].groupby("slot"):
        piv = g.pivot_table(index=["item", "cell", "label"], columns="setting", values="correct", aggfunc="first").dropna()
        x, y, p = mcnemar(piv["off_low"], piv["off_high"])
        recs.append(dict(slot=slot, n=len(piv), acc_low=piv["off_low"].mean(), acc_high=piv["off_high"].mean(),
                         high_gains=y, high_loses=x, p_mcnemar=p))
        sub = piv[piv.index.get_level_values("cell").isin(THAI)]
        if len(sub):
            x, y, p = mcnemar(sub["off_low"], sub["off_high"])
            recs.append(dict(slot=slot + " (Thai cells)", n=len(sub), acc_low=sub["off_low"].mean(), acc_high=sub["off_high"].mean(),
                             high_gains=y, high_loses=x, p_mcnemar=p))
    r = pd.DataFrame(recs)
    r.to_csv(OUT / "resolution_mcnemar.csv", index=False)
    parts.append("### Paired low vs high per item (McNemar)\n\n" + md(r, ".3f") + "\n")
    tc = table(df, ["slot", "setting", "cell"])
    pv = tc.pivot_table(index="cell", columns=["slot", "setting"], values="acc").reindex(CELL_ORDER)
    pv.columns = [f"{a}/{b}" for a, b in pv.columns]
    parts.append("### Accuracy per cell by resolution\n\n" + pv.reset_index().to_markdown(index=False, floatfmt=".3f") + "\n")
    # per-level P(yes) for the px cells at low vs high
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    px_cells = ["c01_base", "c02_bar", "c03_matched", "c04_gibberish", "c08_fill", "c09_bottom", "c10_thai", "c12_thaiwrap"]
    order = ["anchor", "m10", "m3", "p4", "p12", "p30"]
    fig, axes = plt.subplots(2, 4, figsize=(16, 7), sharey=True)
    for ax, cell in zip(axes.flat, px_cells):
        d = df[(df["cell"] == cell) & df["scored"]]
        for (slot, setting), g in d.groupby(["slot", "setting"]):
            py = g.groupby("level")["said_yes"].mean().reindex(order)
            ax.plot(range(len(order)), py.to_numpy(float), ("-" if setting == "off_high" else "--") + "o", ms=3, lw=1, label=f"{slot}/{setting}")
        ax.set_xticks(range(len(order)))
        ax.set_xticklabels(order, fontsize=8)
        ax.set_title(cell, fontsize=10)
        ax.axhline(0.5, color="grey", lw=0.5)
        ax.set_ylim(-0.02, 1.02)
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower right", fontsize=8)
    fig.suptitle("Resolution ablation: P(yes) by level (dashed = low, solid = high)")
    fig.tight_layout()
    fig.savefig(OUT / "resolution_levels.png", dpi=130)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = ["# Subset analyses (paraphrase, transcription, resolution)\n"]
    paraphrase(parts)
    ocr(parts)
    resolution(parts)
    (OUT / "analysis_extra.md").write_text("\n".join(parts), encoding="utf-8")
    print("->", OUT / "analysis_extra.md")


if __name__ == "__main__":
    main()
