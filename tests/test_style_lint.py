"""The enumerable half of voice, tested like everything deterministic.

Positive cases are real drafts from corpus/style_examples.md - Dana's
actual voice must pass its own lint.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

from style_lint import lint_draft


DANA_EXAMPLE_1 = """Marcus — yes to the Denver warehouse walkthrough, no to moving it to
Friday. Thursday 2pm works. Bring the dock utilization numbers.

— Dana"""

DANA_EXAMPLE_5 = """Hi Sam — that slot lands in time I keep blocked. Could we do the same
day at 10:30 instead? My calendar link is below.

— Dana"""


def test_real_dana_examples_pass():
    for draft in (DANA_EXAMPLE_1, DANA_EXAMPLE_5):
        result = lint_draft(draft)
        assert result.passed, result.violations


def test_missing_closing_fails():
    r = lint_draft("Jim — on it. Tom will confirm by morning.")
    assert not r.passed and r.violations[0][0] == "closing"


def test_signature_block_fails():
    r = lint_draft("Thanks!\n\nDana Whitfield\nChief Executive Officer\n- Dana")
    assert not r.passed
    assert any(v[0] == "signature" for v in r.violations)


def test_banned_filler_fails():
    r = lint_draft("Thanks for setting this up! See you then.\n\n- Dana")
    assert any(v[0] == "filler" for v in r.violations)


def test_three_paragraphs_fail():
    draft = "One.\n\nTwo.\n\nThree.\n\n- Dana"
    r = lint_draft(draft)
    assert any(v[0] == "length" for v in r.violations)


def test_verbosity_fails():
    draft = ("word " * 140).strip() + "\n\n- Dana"
    r = lint_draft(draft)
    assert any(v[0] == "brevity" for v in r.violations)


def test_em_dash_closing_accepted():
    r = lint_draft("Quick yes.\n\n— Dana")
    assert r.passed, r.violations


def test_every_violation_names_its_rule():
    r = lint_draft("I'm honored by the invitation. Best regards,\nDana Whitfield")
    assert not r.passed
    rules = {v[0] for v in r.violations}
    assert {"closing", "filler", "signature"}.issubset(rules)
