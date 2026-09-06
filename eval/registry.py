"""Model slots and prompts for the eval runs. Edit here, not in run.py.

Slot = short name used in run ids and analysis. `settings` lists the reasoning
settings that the smoke test (2026-09-06, eval/out/smoke/) showed the API accepts.
`workers` = concurrent requests per slot.
"""

SLOTS = {
    # ---- core grid (owner picks 2026-09-06): reasoning off/on where the API has a control
    "gpt56luna":  {"provider": "openai",     "model": "gpt-5.6-luna",                 "settings": ["off"],       "workers": 8,
                   "note": "one setting (effort none): pilot showed reasoning tokens on 7/36 calls at effort high, no usable contrast"},
    "gpt56sol":   {"provider": "openai",     "model": "gpt-5.6-sol",                  "settings": ["off"],       "workers": 8,
                   "note": "one setting (effort none): pilot showed reasoning tokens on 1/36 calls at effort high"},
    "gemini38":   {"provider": "gemini",     "model": "gemini-3.8-flash",             "settings": ["off", "on"], "workers": 8,
                   "note": "off = thinking_budget=0 (still ~100-500 thought tokens, logged); on = thinking_level=high"},
    "glm53flash": {"provider": "zai",        "model": "glm-5.3-flash",                "settings": ["off", "on"], "workers": 10,
                   "note": "thinking cannot be disabled: off = thinking.effort=low, on = thinking.effort=max"},
    "qwen38":     {"provider": "openrouter", "model": "qwen/qwen3.8-flash",           "settings": ["off", "on"], "workers": 8,
                   "note": "OpenRouter reasoning.enabled false vs true+effort high"},
    "dsv4":       {"provider": "deepseek",   "model": "deepseek-v4-flash-vision-exp", "settings": ["off", "on"], "workers": 8,
                   "note": "direct API; thinking.type disabled vs enabled"},
    # ---- optional / not in the grid
    "gpt55":      {"provider": "openai",     "model": "gpt-5.5",                      "settings": ["off", "on"], "workers": 6,
                   "note": "clean reasoning contrast (none vs high) but 2.5x the price of sol"},
    "terra":      {"provider": "openai",     "model": "gpt-5.6-terra",                "settings": ["off", "on"], "workers": 6,
                   "note": "reasoning member of gpt-5.6 (44-100 reasoning tokens at high)"},
    "glm5v":      {"provider": "zai",        "model": "glm-5v-turbo",                 "settings": ["off", "on"], "workers": 4,
                   "note": "thinking.type disabled vs enabled; true off/on toggle"},
    "typhoon":    {"provider": "typhoon",    "model": "typhoon-ocr-v1.5",             "settings": ["default"],   "workers": 4,
                   "note": "OCR-tuned VLM, the only Typhoon model that accepts images; Thai-tuned slot pending owner decision"},
    "sonnet5":    {"provider": "anthropic",  "model": "claude-sonnet-5",              "settings": ["off", "on"], "workers": 4,
                   "note": "frontier-subset candidate; opus-5 ruled out (cost)"},
}

SETTINGS = {
    "off":     {"reasoning": "off"},
    "on":      {"reasoning": "on"},
    "default": {},
    "off_low": {"reasoning": "off", "detail": "low"},    # resolution ablation (OpenAI detail / Gemini media_resolution)
    "off_high": {"reasoning": "off", "detail": "high"},
}

PROMPTS = {
    "main":  "Does any of the box's content extend beyond or fall outside the box? Answer yes or no.",
    "ocr":   "Read the text in the box.",
    # paraphrases (drafted 2026-09-06, piloted on 5 items x 5 models before the 240-item subset):
    # para1 keeps the polarity of `main` with different wording; para2 reverses the polarity
    # ("yes" = fits), which also measures response bias. Analysis inverts para2 via PROMPT_META.
    "para1": "Look at the box. Is any part of its contents sticking out beyond the box's edges? Answer yes or no.",
    "para2": "Is everything in the box fully contained inside the box's edges, with nothing crossing them? Answer yes or no.",
}

PROMPT_META = {
    "main":  {"task": "yesno", "polarity": +1},
    "para1": {"task": "yesno", "polarity": +1},
    "para2": {"task": "yesno", "polarity": -1},   # model "yes" means fits -> maps to label "no"
    "ocr":   {"task": "transcribe", "polarity": 0},
}
