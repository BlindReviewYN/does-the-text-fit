# Does the Text Fit? — anonymized release for review

Controlled benchmark of text-overflow perception in vision-language models (workshop submission, double-blind).

## Contents
- `gen/` — stimulus generator (Playwright/Chromium renderer, certificates, QC), seed pools, bundled OFL fonts.
- `gen/out/v1/` — the 1,080 stimuli (`<cell>_<level>_<seed>.png`) and `manifest.jsonl` (one record per image: cell, level, label, certificates, model-eye survival, seed and style metadata).
- `eval/` — evaluation harness: provider adapters (`providers.py`), run registry (`registry.py`), cached runner (`run.py`), parser (`parse.py`), analyses (`analyze.py`, `analyze_extra.py`, `contrasts.py`), figures (`figures.py`).
- `eval/out/<run>/responses.jsonl` — every model response with request parameters, token usage and latency (`core`, `paraphrase`, `ocr`, `resolution`, `pilot`).
- `eval/out/core/analysis/`, `eval/out/analysis_extra/`, `eval/out/contrasts/` — tables and figures the paper is derived from.
- `paper/figures/` — the paper's figures.

## Reproduce
```
pip install numpy scipy pillow pandas statsmodels matplotlib playwright openai google-genai anthropic python-dotenv httpx
playwright install chromium
python gen/build.py v1                     # regenerate stimuli (deterministic seeds)
python eval/run.py --run core --slots gpt56luna,gpt56sol,gemini38,glm53flash,qwen38,dsv4 --items all --repeat 3
python eval/analyze.py core && python eval/analyze_extra.py && python eval/contrasts.py && python eval/figures.py
```
API keys are read from a `.env` file three directories above `eval/` (see `providers.py`); adjust `ENV` to your layout.

Known issue disclosed in the paper: 22 Gemini responses in `core` hit the output cap and were scored from a yes/no inside the truncated text (`finish` = `MAX_TOKENS`).

License: code MIT; stimuli and responses CC BY 4.0; fonts under their SIL Open Font Licence.
