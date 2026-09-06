"""Cached, resumable eval runner.

    python eval/run.py --run pilot --slots gpt55,gemini38 --settings off,on --items pilot --repeat 3
    python eval/run.py --run core  --slots gpt55,gemini38,glm5v,qwen38,dsv4 --settings off --items all
    python eval/run.py --run core  --slots typhoon --settings default --items thai
    python eval/run.py --run core  --items all --slots gpt55 --settings off --dry

Job key = (item, slot, setting, prompt, rep). Responses append to
eval/out/<run>/responses.jsonl; existing non-error keys whose stored config
fingerprint `cfg` (provider, model, prompt text, setting params, provider
mapping version, stimulus version) matches the current one are skipped, so a
re-run only fills gaps and a changed configuration re-runs its rows (latest row
per key wins downstream). Errors are retried (3 attempts with backoff, identical
parameters) and, if still failing, written with error text so they count.
Answers are re-parsed at analysis time from the stored text (parser version
recorded per row), so a parser change never requires new API calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PureWindowsPath

sys.path.insert(0, str(Path(__file__).parent))
from parse import PARSER_VERSION  # noqa: E402
from providers import MAPPING_VERSION, ask  # noqa: E402
from registry import PROMPTS, SETTINGS, SLOTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "gen" / "out" / "v1"
MANIFEST = IMG_DIR / "manifest.jsonl"
OUT = ROOT / "eval" / "out"
THAI_CELLS = {"c10_thai", "c11_marks", "c12_thaiwrap"}
TEXT_CELLS = ["c01_base", "c04_gibberish", "c05_wordgap", "c06_decoy", "c07_pill", "c09_bottom", "c10_thai", "c12_thaiwrap"]


def load_manifest():
    rows = [json.loads(l) for l in MANIFEST.open(encoding="utf-8")]
    for r in rows:
        r["id"] = PureWindowsPath(r["path"]).stem if r.get("path") else r.get("id")   # manifest paths are Windows-formatted
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate item ids in manifest"
    return rows


def select_items(rows, spec: str):
    """all | thai | pilot | pilot24 | frontier200 | ocr240 | subset240 | subset300 | ids:a,b,c | file:path"""
    if spec == "all":
        return rows
    if spec == "thai":
        return [r for r in rows if r["cell"] in THAI_CELLS]
    if spec in ("pilot", "pilot24"):
        cells = sorted({r["cell"] for r in rows})
        out = []
        for i, c in enumerate(cells):
            items = [r for r in rows if r["cell"] == c]
            pos = [r for r in items if r["label"] == "yes"]
            neg = [r for r in items if r["label"] == "no"]
            rng = random.Random(1000 + i)
            if spec == "pilot":  # one per cell, alternate label (decoys are all negative)
                pool = pos if (i % 2 == 0 and pos) else neg
                out.append(rng.choice(pool))
            else:
                out.append(rng.choice(pos) if pos else rng.choice(neg))
                out.append(rng.choice(neg))
        return out
    if spec == "frontier200":  # stratified: ~17 per cell, balanced by label within cell where possible
        rng = random.Random(200)
        out = []
        cells = sorted({r["cell"] for r in rows})
        q, extra = divmod(200, len(cells))
        per = [q + (1 if k < extra else 0) for k in range(len(cells))]
        for c, n in zip(cells, per):
            items = [r for r in rows if r["cell"] == c]
            pos = [r for r in items if r["label"] == "yes"]
            neg = [r for r in items if r["label"] == "no"]
            npos = min(len(pos), n // 2)
            pick = rng.sample(pos, npos) + rng.sample(neg, n - npos)
            out.extend(pick)
        return out
    if spec == "ocr240":  # 30 per text cell, 8 cells
        rng = random.Random(240)
        out = []
        for c in TEXT_CELLS:
            items = [r for r in rows if r["cell"] == c]
            out.extend(rng.sample(items, 30))
        return out
    if spec == "subset240":  # paraphrase robustness: 20 per cell, label-balanced where possible
        rng = random.Random(240240)
        out = []
        for c in sorted({r["cell"] for r in rows}):
            items = [r for r in rows if r["cell"] == c]
            pos = [r for r in items if r["label"] == "yes"]
            neg = [r for r in items if r["label"] == "no"]
            npos = min(len(pos), 10)
            out.extend(rng.sample(pos, npos) + rng.sample(neg, 20 - npos))
        return out
    if spec == "subset300":  # resolution ablation: 25 per cell, label-balanced
        rng = random.Random(300)
        out = []
        for c in sorted({r["cell"] for r in rows}):
            items = [r for r in rows if r["cell"] == c]
            pos = [r for r in items if r["label"] == "yes"]
            neg = [r for r in items if r["label"] == "no"]
            npos = min(len(pos), 12)
            out.extend(rng.sample(pos, npos) + rng.sample(neg, 25 - npos))
        return out
    if spec.startswith("ids:") or spec.startswith("file:"):
        want = spec[4:].split(",") if spec.startswith("ids:") else Path(spec[5:]).read_text(encoding="utf-8").split()
        have = {r["id"]: r for r in rows}
        missing = [w for w in want if w not in have]
        if missing:
            raise SystemExit(f"unknown item ids: {missing[:10]}")
        return [have[w] for w in dict.fromkeys(want)]
    raise SystemExit(f"unknown items spec {spec}")


def fingerprint(spec, setting_name, prompt_text, stimulus):
    setting = SETTINGS[setting_name]
    payload = json.dumps({"provider": spec["provider"], "model": spec["model"], "prompt": prompt_text,
                          "setting": setting, "mapping": MAPPING_VERSION[spec["provider"]], "stimulus": stimulus},
                         sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def guard_tail(path: Path) -> int:
    """Isolate a torn last line (interrupted append) so the next append cannot merge with it.
    Returns the number of malformed lines found."""
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("rb") as f:
        f.seek(-1, 2)
        last = f.read(1)
    if last != b"\n":
        with path.open("ab") as f:
            f.write(b"\n")
        print(f"WARNING: {path.name} did not end with a newline; isolated the torn tail", flush=True)
    bad = 0
    for line in path.open(encoding="utf-8"):
        if line.strip():
            try:
                json.loads(line)
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"WARNING: {bad} malformed line(s) in {path.name} (ignored, kept on disk)", flush=True)
    return bad


def job_key(item_id, slot, setting, prompt, rep):
    return f"{item_id}|{slot}|{setting}|{prompt}|{rep}"


def call_with_retry(provider, model, png, prompt_text, setting, attempts=3):
    rep = None
    for a in range(attempts):
        rep = ask(provider, model, png, prompt_text, setting)
        if not rep.error:
            return rep
        e = rep.error.lower()
        transient = any(t in e for t in ("429", "rate", "timeout", "timed out", "502", "503", "504", "overloaded", "connection"))
        if not transient:
            return rep
        time.sleep((2 ** a) * 2 + random.random())
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--slots", required=True, help="comma list of registry slots")
    ap.add_argument("--settings", default=None, help="comma list; default = slot's settings")
    ap.add_argument("--items", default="all")
    ap.add_argument("--prompt", default="main")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--retry-errors", action="store_true", help="re-run keys whose stored row has an error or is unparsed (latest row wins)")
    args = ap.parse_args()

    prompt_text = PROMPTS.get(args.prompt)
    if not prompt_text:
        raise SystemExit(f"prompt {args.prompt} not written yet")
    rows = load_manifest()
    items = select_items(rows, args.items)
    stimulus = IMG_DIR.name
    out_dir = OUT / args.run
    out_dir.mkdir(parents=True, exist_ok=True)
    resp_path = out_dir / "responses.jsonl"
    guard_tail(resp_path)

    slots = list(dict.fromkeys(s for s in args.slots.split(",") if s))
    unknown = [s for s in slots if s not in SLOTS]
    if unknown:
        raise SystemExit(f"unknown slots: {unknown}; known: {sorted(SLOTS)}")
    req_settings = list(dict.fromkeys(args.settings.split(","))) if args.settings else None
    if req_settings:
        bad = [s for s in req_settings if s not in SETTINGS]
        if bad:
            raise SystemExit(f"unknown settings: {bad}; known: {sorted(SETTINGS)}")

    done = {}
    if resp_path.exists():
        for line in resp_path.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[r["key"]] = r   # latest row per key wins

    cfgs = {(slot, st): fingerprint(SLOTS[slot], st, prompt_text, stimulus)
            for slot in slots for st in (req_settings or SLOTS[slot]["settings"])}

    def usable(r, slot, st):
        if r.get("cfg") != cfgs[(slot, st)]:
            return False                      # different model / prompt / params / mapping / stimulus
        if args.retry_errors and (r.get("error") or r.get("answer") == "unparsed"):
            return False
        return True

    jobs, skipped, stale = [], 0, 0
    for slot in slots:
        for setting in (req_settings or SLOTS[slot]["settings"]):
            for it in items:
                for rep in range(args.repeat):
                    k = job_key(it["id"], slot, setting, args.prompt, rep)
                    r = done.get(k)
                    if r is not None and usable(r, slot, setting):
                        skipped += 1
                        continue
                    if r is not None and r.get("cfg") != cfgs[(slot, setting)]:
                        stale += 1
                    jobs.append((k, slot, setting, it, rep))
    assert len({j[0] for j in jobs}) == len(jobs), "duplicate job keys"
    print(f"run={args.run} items={len(items)} slots={slots} jobs={len(jobs)} (cached {skipped}, stale-config {stale})", flush=True)
    if args.dry or not jobs:
        by = {}
        for j in jobs:
            by[(j[1], j[2])] = by.get((j[1], j[2]), 0) + 1
        for k, v in sorted(by.items()):
            print("  ", k, v)
        return

    lock = threading.Lock()
    stats = {"ok": 0, "err": 0, "unparsed": 0, "t0": time.time()}
    png_cache = {}

    def do(job):
        k, slot, setting, it, rep = job
        spec = SLOTS[slot]
        png = png_cache.get(it["id"])
        if png is None:
            png = (IMG_DIR / f"{it['id']}.png").read_bytes()
            png_cache[it["id"]] = png
        r = call_with_retry(spec["provider"], spec["model"], png, prompt_text, SETTINGS[setting])
        row = {"key": k, "item": it["id"], "cell": it["cell"], "level": it["level"], "label": it["label"],
               "slot": slot, "provider": spec["provider"], "model": spec["model"], "setting": setting,
               "prompt": args.prompt, "rep": rep, "answer": r.answer, "parser": PARSER_VERSION, "text": r.text,
               "reasoning_len": len(r.reasoning), "usage": r.usage, "latency": round(r.latency, 2),
               "params": r.params, "finish": r.finish, "error": r.error, "cfg": cfgs[(slot, setting)],
               "stimulus": stimulus, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with lock:
            # one unbuffered O_APPEND write per row: safe when a second runner process appends to the same log
            fd = os.open(resp_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0))
            try:
                os.write(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
            finally:
                os.close(fd)
            stats["err"] += bool(r.error)
            stats["unparsed"] += r.answer == "unparsed"
            stats["ok"] += not r.error
            n = stats["ok"] + stats["err"]
            if n % 25 == 0 or n == len(jobs):
                el = time.time() - stats["t0"]
                print(f"  {n}/{len(jobs)} ok={stats['ok']} err={stats['err']} unparsed={stats['unparsed']} "
                      f"{el:.0f}s ({n/el*60:.0f}/min)", flush=True)
        return row

    # one pool per slot so a slow provider does not starve the others
    pools = {}
    futs = []
    for job in jobs:
        slot = job[1]
        if slot not in pools:
            pools[slot] = ThreadPoolExecutor(max_workers=SLOTS[slot].get("workers", 4))
        futs.append(pools[slot].submit(do, job))
    for f in as_completed(futs):
        f.result()
    for p in pools.values():
        p.shutdown()
    el = time.time() - stats["t0"]
    print(f"done: ok={stats['ok']} err={stats['err']} unparsed={stats['unparsed']} in {el:.0f}s -> {resp_path}")


if __name__ == "__main__":
    main()
