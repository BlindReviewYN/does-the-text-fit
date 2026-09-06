"""One-off (2026-09-06): stamp `cfg` fingerprints onto rows written before the fingerprint existed.

Only rows whose request construction is unchanged get the current fingerprint:
openai, openrouter, gemini (mapping v1 unchanged) and deepseek (the only change is
the name of the output-cap field, and the cap never bound: all finish=stop).
GLM (zai) rows are left without cfg on purpose: their reasoning-effort field was
ignored by the server, so both arms are re-run.

    python eval/backfill_cfg.py core
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run import IMG_DIR, fingerprint  # noqa: E402
from registry import PROMPTS, SLOTS  # noqa: E402

run = sys.argv[1]
path = Path(__file__).resolve().parents[1] / "eval" / "out" / run / "responses.jsonl"
backup = path.with_suffix(".jsonl.bak")
shutil.copy(path, backup)
KEEP = {"openai", "openrouter", "gemini", "deepseek"}
stamped, left, bad = 0, 0, 0
out = []
for line in path.open(encoding="utf-8"):
    if not line.strip():
        continue
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        bad += 1
        continue
    if "cfg" not in r and r["provider"] in KEEP and not r.get("error"):
        r["cfg"] = fingerprint(SLOTS[r["slot"]], r["setting"], PROMPTS[r["prompt"]], IMG_DIR.name)
        r["stimulus"] = IMG_DIR.name
        r.setdefault("parser", "v1")
        r.setdefault("cfg_note", "backfilled 2026-09-06: request construction unchanged")
        stamped += 1
    elif "cfg" not in r:
        left += 1
    out.append(json.dumps(r, ensure_ascii=False))
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"stamped={stamped} left_without_cfg={left} malformed_dropped={bad} backup={backup.name}")
