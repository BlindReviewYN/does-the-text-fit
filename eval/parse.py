"""Answer parsing for the yes/no task.

PARSER_VERSION is part of the run fingerprint; bump it when the rule changes.

v2 rule (2026-09-06, replaces v1 "last yes/no wins" after the Codex review showed
"Yes. ... no right-side padding" being read as "no"):
  1. normalise: strip markdown emphasis, lowercase
  2. explicit answer statement wins, last one if several:
       "answer: yes", "answer is no", "final answer: yes", "so the answer is no", "in short: yes"
  3. else a line that is just "yes"/"no" (with punctuation) wins, last such line
  4. else the leading word of the text if it is yes/no ("Yes, the text ...", "No.")
  5. else if exactly one of yes/no occurs as a whole word anywhere, that one
  6. else "unparsed" (never silently mapped)
"""
from __future__ import annotations

import re

PARSER_VERSION = "v2"

_EMPH = re.compile(r"[*_`#>]+")
_EXPLICIT = re.compile(r"(?:final answer|answer|verdict|conclusion|in short|so)\s*(?:is|:|=|-)?\s*[\"'(]*\b(yes|no)\b", re.I)
_LINE = re.compile(r"^\W*(yes|no)\W*$", re.I)
_LEAD = re.compile(r"^\W*(yes|no)\b", re.I)
_WORD = re.compile(r"\b(yes|no)\b", re.I)


def parse_yes_no(text: str) -> str:
    if not text:
        return "unparsed"
    t = _EMPH.sub("", text).strip()
    m = _EXPLICIT.findall(t)
    if m:
        return m[-1].lower()
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    only = [ln for ln in lines if _LINE.match(ln)]
    if only:
        return _LINE.match(only[-1]).group(1).lower()
    m = _LEAD.match(t)
    if m:
        return m.group(1).lower()
    words = {w.lower() for w in _WORD.findall(t)}
    if len(words) == 1:
        return words.pop()
    return "unparsed"


def parse_v1(text: str) -> str:
    ms = _WORD.findall(text or "")
    return ms[-1].lower() if ms else "unparsed"


if __name__ == "__main__":
    tests = {
        "Yes.": "yes", "No": "no", "**Yes**, the text extends beyond the box": "yes",
        "Yes. The label sits inside the box with no right-side padding.": "yes",
        "Looking at the image, the text fits. No.": "no",
        "The text does not fit.\n\n**Answer: yes**": "yes",
        "There is no overflow, so the answer is no.": "no",
        "No, nothing extends beyond. Yes, it is tight but inside.": "unparsed",
        "": "unparsed", "I cannot tell.": "unparsed",
        "Yes\n\nThe text \"View all\" extends beyond the right edge.": "yes",
        "The content stays inside the box.\nNo": "no",
    }
    bad = 0
    for s, want in tests.items():
        got = parse_yes_no(s)
        if got != want:
            bad += 1
            print("FAIL", repr(s), "->", got, "want", want)
    print("parser self-test:", "ok" if not bad else f"{bad} failures")
