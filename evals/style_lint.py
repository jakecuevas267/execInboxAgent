"""Deterministic style lint: the enumerable half of "sounds like Dana."

Iteration 6 insight: the original voice rubric bundled mechanical,
checkable criteria (structure, closing, banned filler) with genuine
judgment ("would Dana say it this way?"). Calibration showed 69%
judge-human agreement with disagreements in both directions - the rubric
was underspecified. The fix follows the project's own rule: deterministic
where enumerable, judge only where judgment is real. These checks are the
enumerable half, extracted into code; the judge keeps only the residue.

Derived directly from corpus/style_examples.md (including its
anti-examples section).
"""

import re
from dataclasses import dataclass

# Phrases Dana never writes (style corpus anti-examples + filler caught
# by the judge in v2 drafts). Lowercase substring match.
BANNED_PHRASES = [
    "per my last email",
    "circling back",
    "thank you for reaching out",
    "thanks for reaching out",
    "your message is important",
    "i'm honored",
    "i am honored",
    "thanks for setting this up",
    "thanks for flagging",
    "i hope this finds you well",
    "please don't hesitate",
    "best regards",
    "kind regards",
    "warm regards",
]

# A signature block is anything after the "- Dana" close, or a formal
# title/full-name sign-off anywhere.
_SIGNATURE_PATTERNS = [
    r"dana\s+whitfield",           # full name = signature block, not Dana
    r"chief executive",
    r"meridian logistics",         # company name in a sign-off
]

_CLOSING = re.compile(r"^[-—–]\s*dana\s*$", re.IGNORECASE)

MAX_PARAGRAPHS = 2
MAX_WORDS = 120


@dataclass(frozen=True)
class LintResult:
    passed: bool
    violations: tuple  # (rule, detail) pairs - every failure names itself


def lint_draft(draft: str) -> LintResult:
    violations = []
    text = (draft or "").strip()
    lower = text.lower()

    lines = [ln.strip() for ln in text.splitlines()]
    non_empty = [ln for ln in lines if ln]

    # Rule 1: closes with "- Dana" (or em/en dash), nothing after it.
    if not non_empty or not _CLOSING.match(non_empty[-1]):
        violations.append(("closing", "must end with '- Dana' as the last line"))

    # Rule 2: at most 2 paragraphs (blank-line separated), closing excluded.
    body = text
    if non_empty and _CLOSING.match(non_empty[-1]):
        body = text[: text.lower().rfind(non_empty[-1].lower())]
    paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    if len(paragraphs) > MAX_PARAGRAPHS:
        violations.append(("length", f"{len(paragraphs)} paragraphs; max {MAX_PARAGRAPHS}"))

    # Rule 3: brevity - Dana's real emails run ~40-70 words.
    words = len(re.findall(r"\S+", body))
    if words > MAX_WORDS:
        violations.append(("brevity", f"{words} words; max {MAX_WORDS}"))

    # Rule 4: no banned filler.
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            violations.append(("filler", f"banned phrase: {phrase!r}"))

    # Rule 5: no signature-block markers.
    for pat in _SIGNATURE_PATTERNS:
        if re.search(pat, lower):
            violations.append(("signature", f"sign-off pattern: /{pat}/"))

    return LintResult(passed=not violations, violations=tuple(violations))
