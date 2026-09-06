"""Pre-registered pooled-over-models contrasts (02-overflow-benchmark-design.md, "Headline contrasts").

    python eval/contrasts.py            # -> eval/out/contrasts/contrasts.md (+ csv)

Estimation (statsmodels): percentage-point differences from a linear probability model (OLS) with
cluster-robust standard errors; odds ratios from a logistic GLM with cluster-robust standard errors,
flagged "separated" when a coefficient exceeds |8| (a category with 0 % or 100 % outcomes).
Cluster = the shared image unit (seed x level "pair" for cells that share seeds; the image itself
otherwise); model (slot) is a fixed effect, so every estimate is "pooled over models".
Primary data: run `core`, prompt `main`, rep 0, reasoning OFF arms of all six models
(Luna, Sol, Gemini, GLM, Qwen, DeepSeek). Robustness: the reasoning ON arms (four models).
Cell 11 is analysed only in its own section. (A binomial GEE with exchangeable correlation was the
first attempt and failed numerically on identity links and separated cells; 2026-09-06.)
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).parent))
from analyze_extra import cer, load_run  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "out" / "contrasts"
MANIFEST = ROOT / "gen" / "out" / "v1" / "manifest.jsonl"
NAMES = {"gemini38": "Gemini 3.8 Flash", "glm53flash": "GLM-5.3-Flash", "gpt56sol": "GPT-5.6 Sol",
         "qwen38": "Qwen 3.8 Flash", "gpt56luna": "GPT-5.6 Luna", "dsv4": "DeepSeek V4 Flash"}


def manifest():
    man = []
    for line in MANIFEST.open(encoding="utf-8"):
        r = json.loads(line)
        r["item"] = PureWindowsPath(r["path"]).stem
        r["ink_px"] = r["cert"].get("ink_px")
        man.append(r)
    m = pd.DataFrame(man)
    return m[["item", "sid", "ink_px", "note", "string"]]


def data(setting="off"):
    df = load_run("core")
    df = df[(df["prompt"] == "main") & (df["rep"] == 0) & (df["setting"] == setting) & df["scored"]].copy()
    df = df.merge(manifest(), on="item", how="left")
    df["pair"] = df["sid"] + "|" + df["level"]        # shared seed x level across cells 1/2/3/4/8
    df["yes"] = df["said_yes"].astype(int)
    df["corr"] = df["correct"].astype(int)
    df["pos"] = (df["label"] == "yes").astype(int)
    return df


def gee(formula, d, cluster, link="identity"):
    """identity -> OLS linear probability model; logit -> logistic GLM. Both with cluster-robust SEs."""
    groups = pd.factorize(d[cluster])[0]
    if link == "identity":
        return smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": groups})
    model = smf.glm(formula, data=d, family=sm.families.Binomial())
    return model.fit(cov_type="cluster", cov_kwds={"groups": groups}, maxiter=200)


def term(res, name, link):
    b, se, p = res.params[name], res.bse[name], res.pvalues[name]
    lo, hi = b - 1.96 * se, b + 1.96 * se
    if link == "identity":
        return dict(est=f"{100*b:+.1f} pp", ci=f"[{100*lo:+.1f}, {100*hi:+.1f}]", p=p)
    if abs(b) > 8 or not np.isfinite(se) or se > 50:
        return dict(est="separated", ci="", p=np.nan)
    return dict(est=f"OR {np.exp(b):.2f}", ci=f"[{np.exp(lo):.2f}, {np.exp(hi):.2f}]", p=p)


def both(formula, d, cluster, name):
    rows = {}
    for link in ("identity", "logit"):
        try:
            rows[link] = term(gee(formula, d, cluster, link), name, link)
        except Exception as e:  # noqa: BLE001
            rows[link] = dict(est="n/a", ci=str(e)[:40], p=np.nan)
    return rows


def marginal(d, by, outcome):
    """Model-averaged rate: mean over models of the per-model rate (equal weight per model)."""
    return d.groupby(by + ["slot"])[outcome].mean().groupby(by).mean()


def fmt_p(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return ""
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def contrast_table(recs):
    return pd.DataFrame(recs).to_markdown(index=False)


# ----------------------------------------------------------------------------- 1. gibberish vs text
def c1_gibberish(d, tag, parts, recs):
    cells = ["c01_base", "c04_gibberish", "c02_bar", "c03_matched"]
    x = d[d["cell"].isin(cells)].copy()
    x["cell"] = pd.Categorical(x["cell"], cells)
    x["ink_z"] = (x["ink_px"] - x["ink_px"].mean()) / x["ink_px"].std()
    parts.append(f"### 1. Gibberish vs text (cells 4 vs 1), with solid-bar and matched-bar controls — {tag}\n")
    m = marginal(x, ["cell"], "corr")
    parts.append("Model-averaged accuracy: " + ", ".join(f"{c} {m[c]:.3f}" for c in cells) + "\n")
    for outcome, sub, label in [("corr", x, "accuracy, all levels"), ("yes", x[x["pos"] == 1], "hit rate (positives)"),
                                ("yes", x[x["pos"] == 0], "false-alarm rate (negatives)")]:
        for cov in ("", " + ink_z"):
            r = both(f"{outcome} ~ C(cell) + C(slot){cov}", sub, "pair", "C(cell)[T.c04_gibberish]")
            recs.append(dict(contrast="gibberish - text", arm=tag, outcome=label + (" | ink covaried" if cov else ""),
                             pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                             OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
        for other in ("c02_bar", "c03_matched"):
            r = both(f"{outcome} ~ C(cell) + C(slot)", sub, "pair", f"C(cell)[T.{other}]")
            recs.append(dict(contrast=f"{other} - text", arm=tag, outcome=label, pp=r["identity"]["est"], pp_ci=r["identity"]["ci"],
                             p_pp=fmt_p(r["identity"]["p"]), OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    # per-model differences for the reader
    pm = x[x["cell"].isin(["c01_base", "c04_gibberish"])].groupby(["slot", "cell"], observed=True)["corr"].mean().unstack()
    pm["diff_pp"] = 100 * (pm["c04_gibberish"] - pm["c01_base"])
    parts.append("Per model (accuracy text / gibberish / difference):\n\n" + pm.round(3).to_markdown() + "\n")


# ----------------------------------------------------------------------------- 2. word-gap vs decoy
def c2_grouping(d, tag, parts, recs):
    x = d[d["cell"].isin(["c05_wordgap", "c06_decoy"])].copy()
    x["kind"] = np.where(x["cell"] == "c06_decoy", "decoy",
                         np.where(x["pos"] == 1, "wordgap_pos", "wordgap_neg"))
    x["kind"] = pd.Categorical(x["kind"], ["wordgap_neg", "decoy", "wordgap_pos"])
    parts.append(f"### 3. Word-gap vs decoy (grouping; cells 5 vs 6, matched seeds) — {tag}\n")
    m = marginal(x, ["kind"], "yes")
    parts.append("Model-averaged P(yes): " + ", ".join(f"{k} {m[k]:.3f}" for k in ["wordgap_neg", "decoy", "wordgap_pos"]) + "\n")
    z = x[x["kind"] != "wordgap_pos"].copy()
    z["kind"] = pd.Categorical(z["kind"].astype(str), ["wordgap_neg", "decoy"])
    r = both("yes ~ C(kind) + C(slot)", z, "sid", "C(kind)[T.decoy]")
    recs.append(dict(contrast="P(yes) decoy - word-gap negatives", arm=tag, outcome="false alarms on a separate control vs a fitting run",
                     pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                     OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    y = x[x["kind"] != "wordgap_neg"].copy()
    y["kind"] = pd.Categorical(y["kind"].astype(str), ["decoy", "wordgap_pos"])
    r = both("yes ~ C(kind) + C(slot)", y, "sid", "C(kind)[T.wordgap_pos]")
    recs.append(dict(contrast="P(yes) word-gap positives - decoy", arm=tag, outcome="discrimination: spilled word vs separate control",
                     pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                     OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    # decoy sub-axes
    dd = x[x["kind"] == "decoy"].copy()
    dd["phrase"] = dd["level"].str.split("_").str[0]
    dd["gap"] = dd["level"].str.split("_").str[1]
    dd["phrase"] = pd.Categorical(dd["phrase"], ["complete", "incomplete"])
    dd["gap"] = pd.Categorical(dd["gap"], ["g30", "g12", "gTwin"])
    r = both("yes ~ C(phrase) + C(gap) + C(slot)", dd, "sid", "C(phrase)[T.incomplete]")
    recs.append(dict(contrast="decoy FA: incomplete - complete phrase", arm=tag, outcome="within decoys, gap covaried",
                     pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                     OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    for g in ("g12", "gTwin"):
        r = both("yes ~ C(phrase) + C(gap) + C(slot)", dd, "sid", f"C(gap)[T.{g}]")
        recs.append(dict(contrast=f"decoy FA: gap {g} - g30", arm=tag, outcome="within decoys, phrase covaried",
                         pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                         OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    pm = dd.groupby(["slot", "phrase"], observed=True)["yes"].mean().unstack()
    parts.append("Decoy false-alarm rate per model by in-box phrase:\n\n" + pm.round(3).to_markdown() + "\n")


# ----------------------------------------------------------------------------- 4. script double difference
def c4_script(d, tag, parts, recs, ocr_cond=None):
    cells = ["c01_base", "c05_wordgap", "c10_thai"]
    x = d[d["cell"].isin(cells)].copy()
    if ocr_cond is not None:
        x = x.merge(ocr_cond, on=["item", "slot"], how="inner")
        x = x[x["readable"]]
    x["cell"] = pd.Categorical(x["cell"], cells)
    head = f"### 4. Script as a double difference: (cell 10 − cell 1) vs (cell 5 − cell 1) — {tag}" + \
           (" — restricted to items the model transcribed with CER < 0.3" if ocr_cond is not None else "") + "\n"
    parts.append(head)
    m = marginal(x, ["cell"], "corr")
    parts.append("Model-averaged accuracy: " + ", ".join(f"{c} {m[c]:.3f}" for c in cells) + f" (n = {len(x)})\n")
    for outcome, sub, label in [("corr", x, "accuracy"), ("yes", x[x["pos"] == 1], "hit rate"), ("yes", x[x["pos"] == 0], "false-alarm rate")]:
        for link in ("identity", "logit"):
            try:
                res = gee(f"{outcome} ~ C(cell) + C(slot)", sub, "item", link)
                b10, b5 = res.params["C(cell)[T.c10_thai]"], res.params["C(cell)[T.c05_wordgap]"]
                # double difference = b10 - b5 ; variance from the covariance matrix
                cov = res.cov_params()
                v = cov.loc["C(cell)[T.c10_thai]", "C(cell)[T.c10_thai]"] + cov.loc["C(cell)[T.c05_wordgap]", "C(cell)[T.c05_wordgap]"] \
                    - 2 * cov.loc["C(cell)[T.c10_thai]", "C(cell)[T.c05_wordgap]"]
                dd = b10 - b5
                se = np.sqrt(v)
                from scipy.stats import norm
                p = 2 * (1 - norm.cdf(abs(dd / se)))
                if link == "logit" and (abs(b10) > 8 or abs(b5) > 8 or not np.isfinite(se) or se > 50):
                    est = dict(OR="separated", OR_ci="", p_or="")
                    key = (label, tag, ocr_cond is not None)
                    rec = next((r for r in recs if r.get("_key") == key), None)
                    if rec is None:
                        rec = dict(contrast="script double difference (10−1) − (5−1)", arm=tag + (" | OCR-conditioned" if ocr_cond is not None else ""),
                                   outcome=label, _key=key)
                        recs.append(rec)
                    rec.update(est)
                    continue
                if link == "identity":
                    est = dict(pp=f"{100*dd:+.1f} pp", pp_ci=f"[{100*(dd-1.96*se):+.1f}, {100*(dd+1.96*se):+.1f}]", p_pp=fmt_p(p),
                               d10=f"{100*b10:+.1f} pp", d5=f"{100*b5:+.1f} pp")
                else:
                    est = dict(OR=f"OR {np.exp(dd):.2f}", OR_ci=f"[{np.exp(dd-1.96*se):.2f}, {np.exp(dd+1.96*se):.2f}]", p_or=fmt_p(p))
                key = (label, tag, ocr_cond is not None)
                rec = next((r for r in recs if r.get("_key") == key), None)
                if rec is None:
                    rec = dict(contrast="script double difference (10−1) − (5−1)", arm=tag + (" | OCR-conditioned" if ocr_cond is not None else ""),
                               outcome=label, _key=key)
                    recs.append(rec)
                rec.update(est)
            except Exception as e:  # noqa: BLE001
                recs.append(dict(contrast="script double difference", arm=tag, outcome=label, pp=f"n/a ({str(e)[:40]})"))
    pm = x.groupby(["slot", "cell"], observed=True)["corr"].mean().unstack()
    pm["(10-1)"] = pm["c10_thai"] - pm["c01_base"]
    pm["(5-1)"] = pm["c05_wordgap"] - pm["c01_base"]
    pm["double"] = pm["(10-1)"] - pm["(5-1)"]
    parts.append("Per model (accuracy):\n\n" + pm.round(3).to_markdown() + "\n")


# ----------------------------------------------------------------------------- 2. rect vs pill
def c5_pill(d, tag, parts, recs):
    x = d[d["cell"].isin(["c01_base", "c07_pill"])].copy()
    x["shape"] = np.where(x["cell"] == "c07_pill", "pill", "rect")
    x["shape"] = pd.Categorical(x["shape"], ["rect", "pill"])
    parts.append(f"### 2. Rect vs pill (cells 1 vs 7; bounding-box shortcut) — {tag}\n")
    pos = x[(x["pos"] == 1) & x["level"].isin(["p4", "p12"])].copy()      # matched positive levels
    m = marginal(pos, ["shape"], "yes")
    parts.append(f"Model-averaged hit rate at +4/+12 px: rect {m['rect']:.3f}, pill {m['pill']:.3f}\n")
    r = both("yes ~ C(shape) + C(level) + C(slot)", pos, "item", "C(shape)[T.pill]")
    recs.append(dict(contrast="hit rate pill - rect (+4/+12 px)", arm=tag, outcome="matched positive levels",
                     pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                     OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    neg = x[x["pos"] == 0].copy()
    r = both("yes ~ C(shape) + C(level) + C(slot)", neg, "item", "C(shape)[T.pill]")
    recs.append(dict(contrast="false-alarm rate pill - rect", arm=tag, outcome="negatives (anchor/−10/−3)",
                     pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                     OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    corner = x[(x["cell"] == "c07_pill") & (x["level"] == "corner")]
    rect4 = x[(x["cell"] == "c01_base") & (x["level"] == "p4")]
    cc = pd.concat([corner.assign(kind="corner"), rect4.assign(kind="rect_p4")])
    cc["kind"] = pd.Categorical(cc["kind"], ["rect_p4", "corner"])
    r = both("yes ~ C(kind) + C(slot)", cc, "item", "C(kind)[T.corner]")
    recs.append(dict(contrast="hit rate pill corner-cross - rect +4 px", arm=tag, outcome="ink inside the bounding box but across the curve",
                     pp=r["identity"]["est"], pp_ci=r["identity"]["ci"], p_pp=fmt_p(r["identity"]["p"]),
                     OR=r["logit"]["est"], OR_ci=r["logit"]["ci"], p_or=fmt_p(r["logit"]["p"])))
    pm = x[x["pos"] == 1].groupby(["slot", "cell", "level"], observed=True)["yes"].mean().unstack("level")
    parts.append("Per model hit rate by level:\n\n" + pm.round(2).to_markdown() + "\n")


# ----------------------------------------------------------------------------- 5. cell 11 x OCR
def c6_marks(d, tag, parts):
    x = d[d["cell"] == "c11_marks"].copy()
    ocr = load_run("ocr")
    man = manifest().set_index("item")
    ocr = ocr[ocr["cell"].isin(["c10_thai", "c12_thaiwrap"])].copy()
    ocr["cer"] = [cer(t, [man.loc[i, "string"]]) for t, i in zip(ocr["text"], ocr["item"])]
    thai_cer = ocr.groupby("slot")["cer"].median().rename("thai_median_cer")
    t = x.groupby("slot").agg(acc=("corr", "mean"), hit=("yes", lambda s: s[x.loc[s.index, "pos"] == 1].mean()),
                              fa=("yes", lambda s: s[x.loc[s.index, "pos"] == 0].mean())).join(thai_cer)
    by_level = x.groupby(["slot", "level"])["yes"].mean().unstack("level")[["anchor", "m1", "m3", "p3", "p6", "p9"]]
    parts.append(f"### 5. Cell 11 (protruding Thai marks) × Thai transcription success — {tag}\n\n"
                 "Cell 11 was not in the transcription probe; Thai readability is the model's median CER on cells 10 and 12 "
                 "(30 items each). Reported per model, never pooled.\n\n" + t.round(3).to_markdown() + "\n\nP(yes) by level:\n\n"
                 + by_level.round(2).to_markdown() + "\n")


def ocr_condition():
    """(item, slot) -> readable flag from the transcription probe (CER < 0.3), where available."""
    ocr = load_run("ocr")
    man = manifest().set_index("item")
    out = []
    for _, r in ocr.iterrows():
        refs = [man.loc[r["item"], "string"]]
        note = man.loc[r["item"], "note"] or ""
        if "word=" in note:
            refs.append(man.loc[r["item"], "string"] + " " + note.split("word=")[1].split(";")[0])
        out.append(dict(item=r["item"], slot=r["slot"], readable=cer(r["text"], refs) < 0.3))
    return pd.DataFrame(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parts = ["# Pre-registered pooled contrasts (GEE, cluster-robust; model as fixed effect)\n",
             "Primary arm = reasoning OFF, six models, rep 0. Robustness arm = reasoning ON, four models. "
             "`pp` = model-pooled percentage-point difference (identity link); `OR` = odds ratio (logit link). "
             "Cluster = seed × level pair where cells share seeds (1/2/3/4/8; 5/6 by seed), else the image.\n"]
    recs = []
    d_off, d_on = data("off"), data("on")
    oc = ocr_condition()
    for tag, d in (("reasoning off (6 models)", d_off), ("reasoning on (4 models)", d_on)):
        c1_gibberish(d, tag, parts, recs)
        c5_pill(d, tag, parts, recs)
        c2_grouping(d, tag, parts, recs)
        c4_script(d, tag, parts, recs)
        if tag.startswith("reasoning off"):
            c4_script(d, tag, parts, recs, ocr_cond=oc)
    c6_marks(d_off, "reasoning off", parts)
    tab = pd.DataFrame(recs).drop(columns=["_key"], errors="ignore")
    cols = ["contrast", "arm", "outcome", "pp", "pp_ci", "p_pp", "OR", "OR_ci", "p_or", "d10", "d5"]
    tab = tab[[c for c in cols if c in tab.columns]]
    tab.to_csv(OUT / "contrasts.csv", index=False)
    parts.insert(2, "## Summary table\n\n" + tab.to_markdown(index=False) + "\n\n## Detail\n")
    (OUT / "contrasts.md").write_text("\n".join(parts), encoding="utf-8")
    print(tab.to_string())
    print("->", OUT / "contrasts.md")


if __name__ == "__main__":
    main()
