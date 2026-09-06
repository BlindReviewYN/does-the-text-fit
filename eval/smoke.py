"""Provider smoke test: 5 images x each (provider, model, setting); records accepted params.

    python eval/smoke.py                # all targets
    python eval/smoke.py openai gemini  # subset of providers
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from providers import ask  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "gen" / "out" / "v1"
OUT = ROOT / "eval" / "out" / "smoke"
PROMPT = "Does any of the box's content extend beyond or fall outside the box? Answer yes or no."

ITEMS = [  # id, label
    ("c01_base_p12_en00", "yes"),
    ("c01_base_m3_en01", "no"),
    ("c07_pill_corner_pill02", "yes"),
    ("c06_decoy_incomplete_gTwin_en03", "no"),
    ("c11_marks_p6_thm04", "yes"),
]

R_OFF, R_ON = {"reasoning": "off"}, {"reasoning": "on"}
TARGETS = [
    # provider, model, [settings]
    ("openai", "gpt-5.5", [R_OFF, R_ON, {"reasoning": "off", "detail": "low"}, {"reasoning": "off", "detail": "high"}]),
    ("openai", "gpt-5.6-luna", [R_OFF, R_ON]),
    ("openai", "gpt-5.6-sol", [R_OFF, R_ON]),
    ("gemini", "gemini-3.8-flash", [R_OFF, R_ON, {"reasoning": "off", "detail": "low"}, {"reasoning": "off", "detail": "high"}]),
    ("gemini", "gemini-3.7-flash", [R_OFF, R_ON]),
    ("zai", "glm-5.3-flash", [R_OFF, R_ON]),
    ("zai", "glm-5v-turbo", [R_OFF, R_ON]),
    ("zai", "glm-4.6v", [R_OFF, R_ON]),
    ("openrouter", "qwen/qwen3.8-flash", [R_OFF, R_ON]),
    ("openrouter", "z-ai/glm-5.3-flash", [R_OFF, R_ON]),
    ("deepseek", "deepseek-v4-flash-vision-exp", [R_OFF, R_ON]),
    ("openrouter", "deepseek/deepseek-v4-flash-vision-exp", [R_OFF, R_ON]),
    ("typhoon", "typhoon-ocr-v1.5", [{}]),
    ("typhoon", "typhoon-v2.5-30b-a3b-instruct", [{}]),
    ("anthropic", "claude-sonnet-5", [R_OFF, R_ON]),
]


def setting_id(s: dict) -> str:
    return "+".join(f"{k}={v}" for k, v in sorted(s.items())) or "default"


def run_target(prov, model, settings):
    rows = []
    for s in settings:
        for iid, label in ITEMS:
            png = (IMG_DIR / f"{iid}.png").read_bytes()
            rep = ask(prov, model, png, PROMPT, s)
            rows.append({"provider": prov, "model": model, "setting": setting_id(s), "item": iid, "label": label,
                         "answer": rep.answer, "text": rep.text[:400], "reasoning_len": len(rep.reasoning),
                         "usage": rep.usage, "latency": round(rep.latency, 2), "params": rep.params,
                         "finish": rep.finish, "error": rep.error})
            print(f"{prov:10} {model:36} {setting_id(s):28} {iid:32} {label:3} -> {rep.answer:8} {rep.latency:5.1f}s "
                  f"{json.dumps(rep.usage)} {rep.params} {rep.error[:80]}", flush=True)
    return rows


def main(argv):
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(argv)
    known = {t[0] for t in TARGETS} | {t[1] for t in TARGETS}
    bad = only - known
    if bad:
        raise SystemExit(f"unknown selector(s) {sorted(bad)}; known: {sorted(known)}")
    targets = [t for t in TARGETS if not only or t[0] in only or t[1] in only]
    if not targets:
        raise SystemExit("no targets selected")
    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(lambda t: run_target(*t), targets):
            rows.extend(r)
    ts = time.strftime("%Y%m%d-%H%M%S")
    (OUT / f"smoke_{ts}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    # summary
    print("\n== summary (correct/5, mean latency, accepted params)")
    seen = {}
    for r in rows:
        k = (r["provider"], r["model"], r["setting"])
        d = seen.setdefault(k, {"n": 0, "ok": 0, "lat": 0.0, "err": 0, "unparsed": 0, "params": r["params"], "e": r["error"]})
        d["n"] += 1
        d["ok"] += r["answer"] == r["label"]
        d["lat"] += r["latency"]
        d["err"] += r["answer"] == "error"
        d["unparsed"] += r["answer"] == "unparsed"
    for k, d in seen.items():
        print(f"{k[0]:10} {k[1]:36} {k[2]:28} ok={d['ok']}/{d['n']} err={d['err']} unparsed={d['unparsed']} "
              f"lat={d['lat']/d['n']:.1f}s params={d['params']} {d['e'][:100]}")
    print("saved", OUT / f"smoke_{ts}.json")


if __name__ == "__main__":
    main(sys.argv[1:])
