"""Provider adapters for the overflow benchmark.

One function per provider with a common signature:

    ask(provider, model, png, prompt, setting) -> Reply

`setting` keys (all optional):
    reasoning: "off" | "on"      -> mapped to each API's own control
    detail:    "low" | "high"    -> image resolution hint where the API has one
    max_tokens: int              -> override output cap

Arm stability (Codex review 2026-09-06, S1): each (provider, model, setting) resolves
its request configuration ONCE — the first candidate the API accepts is locked for
every later call. Candidates are only advanced on a parameter rejection (HTTP 400 /
INVALID_ARGUMENT); transient failures (429, 5xx, timeouts) return an error with the
same parameters so the runner can retry them unchanged. `Reply.params` records the
exact controls and output cap sent.

MAPPING_VERSION is per provider and is part of the run fingerprint: bump it when the
request construction for that provider changes.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from parse import parse_yes_no

ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ENV)

ZAI_BASE = "https://api.z.ai/api/paas/v4"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEEPSEEK_BASE = "https://api.deepseek.com"
TYPHOON_BASE = "https://api.opentyphoon.ai/v1"

MAPPING_VERSION = {
    "openai": "v1",        # chat.completions, reasoning_effort, max_completion_tokens, image detail
    "openrouter": "v1",    # chat.completions, reasoning{enabled,effort}, max_completion_tokens
    "zai": "v2",           # v2: top-level reasoning_effort (nested thinking.effort was ignored), max_tokens
    "deepseek": "v2",      # v2: max_tokens instead of max_completion_tokens (documented field)
    "typhoon": "v2",       # v2: max_tokens
    "gemini": "v1",        # thinking_budget=0 | thinking_level=high, media_resolution
    "anthropic": "v2",     # v2: honours setting max_tokens; adaptive thinking + effort
}

_CLIENTS: dict = {}
_RESOLVED: dict = {}          # lock_key -> index of the accepted candidate
_RESOLVE_LOCK = threading.Lock()


@dataclass
class Reply:
    text: str = ""
    reasoning: str = ""
    usage: dict = field(default_factory=dict)
    latency: float = 0.0
    params: dict = field(default_factory=dict)
    finish: str = ""
    error: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def answer(self) -> str:
        if self.error:
            return "error"
        return parse_yes_no(self.text)


def data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _lock_key(provider, model, setting):
    return f"{provider}|{model}|{json.dumps(setting, sort_keys=True)}"


def _candidates_for(lock_key, cands):
    """Return the candidate list to try: the locked one if resolved, else all in order."""
    r = _RESOLVED.get(lock_key)
    return [(r["idx"], cands[r["idx"]])] if r is not None else list(enumerate(cands))


def _lock(lock_key, idx, **extra):
    with _RESOLVE_LOCK:
        _RESOLVED.setdefault(lock_key, {"idx": idx, **extra})


def _is_param_error(e: Exception) -> bool:
    """True for a request the API rejected as malformed/unsupported (safe to try the next candidate)."""
    status = getattr(e, "status_code", None)
    if status is None:
        status = getattr(getattr(e, "response", None), "status_code", None)
    if status == 400:
        return True
    s = str(e)
    return ("INVALID_ARGUMENT" in s) or ("Error code: 400" in s) or s.startswith("400")


def _usage_from_openai(u) -> dict:
    if u is None:
        return {}
    d = {"in": getattr(u, "prompt_tokens", None), "out": getattr(u, "completion_tokens", None)}
    det = getattr(u, "completion_tokens_details", None)
    if det is not None and getattr(det, "reasoning_tokens", None) is not None:
        d["reasoning"] = det.reasoning_tokens
    return d


# --------------------------------------------------------------------------- OpenAI-compatible
def _oai_client(base: str | None, key_env: str):
    from openai import OpenAI
    k = (base, key_env)
    if k not in _CLIENTS:
        _CLIENTS[k] = OpenAI(api_key=os.environ[key_env], base_url=base, timeout=180, max_retries=1)
    return _CLIENTS[k]


def _oai_chat(client, model, png, prompt, detail, max_tokens, candidates, lock_key,
              cap_param="max_completion_tokens", use_temperature=True):
    """Try candidates in order (or only the locked one); advance only on parameter errors."""
    img = {"type": "image_url", "image_url": {"url": data_url(png)}}
    if detail:
        img["image_url"]["detail"] = detail
    msgs = [{"role": "user", "content": [img, {"type": "text", "text": prompt}]}]
    last_err = ""
    no_temp = (_RESOLVED.get(lock_key) or {}).get("no_temperature", False)
    for idx, cand in _candidates_for(lock_key, candidates):
        kw = dict(cand)
        kw[cap_param] = max_tokens
        if use_temperature and "temperature" not in kw and not no_temp:
            kw["temperature"] = 0
        t0 = time.time()
        try:
            r = client.chat.completions.create(model=model, messages=msgs, **kw)
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:300]}"
            if not _is_param_error(e) or lock_key in _RESOLVED:
                return Reply(error=last_err)   # transient, or arm already locked: same params next time
            if "temperature" in kw and "temperature" in str(e).lower():
                # a rejected temperature is a parameter error: retry this candidate without it
                kw.pop("temperature")
                try:
                    t0 = time.time()
                    r = client.chat.completions.create(model=model, messages=msgs, **kw)
                except Exception as e2:  # noqa: BLE001
                    last_err = f"{type(e2).__name__}: {str(e2)[:300]}"
                    if _is_param_error(e2):
                        continue
                    return Reply(error=last_err)
                no_temp = True
            else:
                continue
        lat = time.time() - t0
        _lock(lock_key, idx, no_temperature=no_temp)
        ch = r.choices[0]
        msg = ch.message
        reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
        params = {k: v for k, v in kw.items() if k != cap_param}
        params["cap"] = {cap_param: max_tokens}
        if detail:
            params["detail"] = detail
        return Reply(text=msg.content or "", reasoning=reasoning or "", usage=_usage_from_openai(r.usage),
                     latency=lat, params=params, finish=ch.finish_reason or "",
                     raw={"id": r.id, "model": getattr(r, "model", None)})
    return Reply(error=last_err or "no candidate accepted")


def _cap(setting, r):
    return setting.get("max_tokens") or (12000 if r == "on" else 512)


def ask_openai(model, png, prompt, setting):
    c = _oai_client(None, "OPENAI_API_KEY")
    r = setting.get("reasoning")
    if r == "off":
        cands = [{"reasoning_effort": "none"}, {"reasoning_effort": "minimal"}]
    elif r == "on":
        cands = [{"reasoning_effort": "high"}]
    else:
        cands = [{}]
    return _oai_chat(c, model, png, prompt, setting.get("detail"), _cap(setting, r), cands,
                     _lock_key("openai", model, setting), use_temperature=False)


def ask_zai(model, png, prompt, setting):
    c = _oai_client(ZAI_BASE, "ZAI_API_KEY")
    r = setting.get("reasoning")
    if r == "off":
        # thinking-only models (glm-5.3-flash) reject disabled -> lowest effort via the TOP-LEVEL
        # field; the nested thinking.effort is ignored by the server (probe 2026-09-06: 20 vs 355 tokens)
        cands = [{"extra_body": {"thinking": {"type": "disabled"}}},
                 {"extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"}}]
    elif r == "on":
        cands = [{"extra_body": {"thinking": {"type": "enabled"}, "reasoning_effort": "max"}},
                 {"extra_body": {"thinking": {"type": "enabled"}}}]
    else:
        cands = [{}]
    return _oai_chat(c, model, png, prompt, None, _cap(setting, r), cands,
                     _lock_key("zai", model, setting), cap_param="max_tokens")


def ask_openrouter(model, png, prompt, setting):
    c = _oai_client(OPENROUTER_BASE, "OPENROUTER_API_KEY")
    r = setting.get("reasoning")
    if r == "off":
        cands = [{"extra_body": {"reasoning": {"enabled": False}}}]
    elif r == "on":
        cands = [{"extra_body": {"reasoning": {"enabled": True, "effort": "high"}}}]
    else:
        cands = [{}]
    return _oai_chat(c, model, png, prompt, setting.get("detail"), _cap(setting, r), cands,
                     _lock_key("openrouter", model, setting))


def ask_deepseek(model, png, prompt, setting):
    c = _oai_client(DEEPSEEK_BASE, "DEEPSEEK_API_KEY")
    r = setting.get("reasoning")
    if r == "off":
        cands = [{"extra_body": {"thinking": {"type": "disabled"}}}]
    elif r == "on":
        cands = [{"extra_body": {"thinking": {"type": "enabled"}}}]
    else:
        cands = [{}]
    return _oai_chat(c, model, png, prompt, None, _cap(setting, r), cands,
                     _lock_key("deepseek", model, setting), cap_param="max_tokens")


def ask_typhoon(model, png, prompt, setting):
    c = _oai_client(TYPHOON_BASE, "TYPHOON_API_KEY")
    return _oai_chat(c, model, png, prompt, None, setting.get("max_tokens") or 512, [{}],
                     _lock_key("typhoon", model, setting), cap_param="max_tokens")


# --------------------------------------------------------------------------- Gemini (native)
def ask_gemini(model, png, prompt, setting):
    from google import genai
    from google.genai import types
    if "gemini" not in _CLIENTS:
        _CLIENTS["gemini"] = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    client = _CLIENTS["gemini"]
    r = setting.get("reasoning")
    if r == "off":
        # 3.x Flash rejects thinking_level=minimal; thinking_budget=0 is accepted but still spends
        # ~100-500 thought tokens (smoke test 2026-09-06). thoughts_token_count is logged per call.
        cands = [("thinking_budget=0", types.ThinkingConfig(thinking_budget=0)),
                 ("thinking_level=low", types.ThinkingConfig(thinking_level="low"))]
    elif r == "on":
        cands = [("thinking_level=high", types.ThinkingConfig(thinking_level="high")),
                 ("thinking_budget=8192", types.ThinkingConfig(thinking_budget=8192))]
    else:
        cands = [("default", None)]
    # Gemini 3 counts thought tokens against max_output_tokens: with budget 0 the model still thinks
    # ~500 tokens, so a 512 cap truncated 16/3240 core calls (2026-09-06). Cap recorded per row.
    mt = setting.get("max_tokens") or (8000 if r == "on" else 2048)
    detail = setting.get("detail")
    media = None
    if detail == "low":
        media = types.MediaResolution.MEDIA_RESOLUTION_LOW
    elif detail == "high":
        media = types.MediaResolution.MEDIA_RESOLUTION_HIGH
    parts = [types.Part.from_bytes(data=png, mime_type="image/png"), prompt]
    lock_key = _lock_key("gemini", model, setting)
    last_err = ""
    for idx, (name, tc) in _candidates_for(lock_key, cands):
        cfg = types.GenerateContentConfig(temperature=0, max_output_tokens=mt, thinking_config=tc, media_resolution=media)
        t0 = time.time()
        try:
            resp = client.models.generate_content(model=model, contents=parts, config=cfg)
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:300]}"
            if _is_param_error(e) and lock_key not in _RESOLVED:
                continue
            return Reply(error=last_err)
        lat = time.time() - t0
        _lock(lock_key, idx)
        um = resp.usage_metadata
        usage = {"in": getattr(um, "prompt_token_count", None), "out": getattr(um, "candidates_token_count", None),
                 "reasoning": getattr(um, "thoughts_token_count", None)}
        try:
            text = resp.text or ""
        except Exception:  # noqa: BLE001
            text = ""
        finish = ""
        try:
            finish = str(resp.candidates[0].finish_reason)
        except Exception:  # noqa: BLE001
            pass
        params = {"thinking": name, "temperature": 0, "cap": {"max_output_tokens": mt}}
        if detail:
            params["media_resolution"] = detail
        return Reply(text=text, usage=usage, latency=lat, params=params, finish=finish,
                     raw={"model_version": getattr(resp, "model_version", None)})
    return Reply(error=last_err or "no candidate accepted")


# --------------------------------------------------------------------------- Anthropic (native)
def ask_anthropic(model, png, prompt, setting):
    import anthropic
    if "anthropic" not in _CLIENTS:
        _CLIENTS["anthropic"] = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=180, max_retries=1)
    client = _CLIENTS["anthropic"]
    r = setting.get("reasoning")
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.b64encode(png).decode()}},
               {"type": "text", "text": prompt}]
    mt = setting.get("max_tokens") or (8000 if r == "on" else 512)
    # Claude 5 family: thinking.type=enabled is rejected ("use adaptive and output_config.effort");
    # temperature is deprecated (400). Smoke test 2026-09-06.
    if r == "on":
        cands = [("thinking=adaptive+effort=high", {"thinking": {"type": "adaptive"}, "output_config": {"effort": "high"}}),
                 ("thinking=adaptive", {"thinking": {"type": "adaptive"}}),
                 ("thinking=enabled/4000", {"thinking": {"type": "enabled", "budget_tokens": 4000}})]
    elif r == "off":
        cands = [("thinking=disabled", {"thinking": {"type": "disabled"}}),
                 ("no-thinking", {})]
    else:
        cands = [("default", {})]
    lock_key = _lock_key("anthropic", model, setting)
    last_err = ""
    for idx, (name, kw) in _candidates_for(lock_key, cands):
        t0 = time.time()
        try:
            resp = client.messages.create(model=model, max_tokens=mt, messages=[{"role": "user", "content": content}], **kw)
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:300]}"
            if _is_param_error(e) and lock_key not in _RESOLVED:
                continue
            return Reply(error=last_err)
        lat = time.time() - t0
        _lock(lock_key, idx)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        think = "".join(getattr(b, "thinking", "") for b in resp.content if getattr(b, "type", "") == "thinking")
        usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
        return Reply(text=text, reasoning=think, usage=usage, latency=lat,
                     params={"thinking": name, "cap": {"max_tokens": mt}},
                     finish=str(resp.stop_reason), raw={"id": resp.id})
    return Reply(error=last_err or "no candidate accepted")


PROVIDERS = {
    "openai": ask_openai,
    "gemini": ask_gemini,
    "zai": ask_zai,
    "openrouter": ask_openrouter,
    "deepseek": ask_deepseek,
    "typhoon": ask_typhoon,
    "anthropic": ask_anthropic,
}


def ask(provider: str, model: str, png: bytes, prompt: str, setting: dict | None = None) -> Reply:
    return PROVIDERS[provider](model, png, prompt, setting or {})
