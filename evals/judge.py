"""LLM judge for draft quality - the genuinely judgment-shaped part.

Rubric v2 (Iteration 6). Calibration of the v1 rubric (voice 69%,
grounded 92%, register 100% agreement with blind human labels) showed
the voice axis was underspecified - the original definition bundled
MECHANICAL criteria (paragraph count, closing, banned filler) with real
judgment ("would Dana say it this way?"). The fix follows the project's
own rule - deterministic where enumerable, judge where judgment is real:

  - The mechanical half of voice moved to code: evals/style_lint.py
    (unit-tested; Dana's own corpus examples pass it). The reported
    voice verdict is a COMPOSITE: lint AND judge.
  - The judge's voice axis narrowed to the residue - directness and
    warmth - with pass/fail anchors in the rubric itself.
  - grounded gained an anchored definition plus CONSENSUS SAMPLING
    (default 3 samples, majority vote): v1 calibration caught the judge
    contradicting itself on e13 across runs, so single-sample judging
    cannot gate this axis.
  - register (100% agreement) is unchanged: you don't rewrite a
    calibrated axis.

Usage:
    python evals/judge.py --results results/v2.json
    python evals/judge.py --results results/v2.json --calibrate --samples 3

Calibration compares the composite voice verdict against the original
holistic human labels (results/human_labels.json), so the labels remain
valid ground truth across the rubric change.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from langchain_anthropic import ChatAnthropic  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from style_lint import lint_draft  # noqa: E402

JUDGE_MODEL = "claude-haiku-4-5"

STYLE = (ROOT / "corpus/style_examples.md").read_text()


class DraftGrade(BaseModel):
    voice: bool = Field(..., description=(
        "Directness and warmth ONLY (structure/closing/filler are checked by "
        "code, not you). PASS if the draft leads with the answer or decision "
        "in the first sentence and reads like a busy human talking to a "
        "specific person. FAIL if it opens with throat-clearing before the "
        "point, hedges instead of deciding, or reads like a form letter. "
        "Anchors - PASS: 'Marcus - yes to the walkthrough, no to Friday.' "
        "FAIL: 'I wanted to follow up regarding the walkthrough we discussed.'"))
    grounded: bool = Field(..., description=(
        "Every specific claim (times, dates, actions taken, commitments, "
        "offers) must appear in the inbound email or the retrieved context. "
        "PASS: proposing something NEW when framed as a proposal ('could we "
        "do 10:30?' citing a listed open slot). A time WITHIN a shown open "
        "range counts as grounded (10:30 is inside 10:00-12:00), and a "
        "weekday name matching a shown date counts (Tuesday = 2026-10-06). "
        "FAIL: asserting an unverified fact as done ('the team re-confirmed "
        "this morning') or proposing a specific time with no basis in the "
        "provided calendar data."))
    register: bool = Field(..., description=(
        "Tone is appropriate for the sender relationship (internal peer vs "
        "external vs VIP)"))
    worst_problem: str = Field(..., description="One sentence: the single biggest issue, or 'none'")


PROMPT = """You are grading a draft email written by an assistant on behalf of \
Dana Whitfield (CEO). Grade STRICTLY against the rubric fields - each field's \
description IS the rubric; apply its anchors literally.

Dana's real style examples:
{style}

The inbound email:
{email}

Context the assistant retrieved before drafting (tool results - claims
grounded in THIS content are grounded):
{context}

The assistant's draft:
{draft}
"""


def majority(votes: list[bool]) -> bool:
    return Counter(votes).most_common(1)[0][0]


def grade_draft(judge, email_text: str, draft: str, samples: int,
                context: str = "") -> dict:
    """Composite grade: deterministic lint + (sampled) judge verdicts."""
    lint = lint_draft(draft)
    ctx = context or "(none captured - results predate tool-output capture; treat unverifiable claims conservatively)"
    runs = [judge.invoke(PROMPT.format(style=STYLE, email=email_text, draft=draft, context=ctx))
            for _ in range(samples)]
    judge_voice = majority([r.voice for r in runs])
    grounded = majority([r.grounded for r in runs])
    register = majority([r.register for r in runs])
    return {
        "voice": lint.passed and judge_voice,       # the composite verdict
        "grounded": grounded,
        "register": register,
        "lint_passed": lint.passed,
        "lint_violations": [f"{rule}: {detail}" for rule, detail in lint.violations],
        "judge_voice": judge_voice,
        "samples": samples,
        "grounded_votes": [r.grounded for r in runs],
        "worst_problem": runs[0].worst_problem,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--samples", type=int, default=3,
                    help="judge samples per draft, majority vote (default 3)")
    ap.add_argument("--labels", default="results/human_labels.json",
                    help="human label file to calibrate against")
    args = ap.parse_args()

    rows = json.loads(Path(args.results).read_text())
    judge = ChatAnthropic(model=JUDGE_MODEL, max_tokens=1024).with_structured_output(DraftGrade)
    dataset = {c["id"]: c for c in json.loads((ROOT / "datasets/golden_inbox.json").read_text())["cases"]}

    graded = {}
    for row in rows:
        draft = (row.get("record", {}).get("decision") or {}).get("draft_text")
        if not draft:
            continue
        email = dataset[row["case_id"]]["email"]
        email_text = f"From: {email['from_name']} <{email['from_email']}>\nSubject: {email['subject']}\n{email['body']}"
        context = "\n\n".join(
            f"[{tr['name']}]\n{tr['content']}"
            for tr in row.get("record", {}).get("tool_results", []))
        g = grade_draft(judge, email_text, draft, args.samples, context=context)
        graded[row["case_id"]] = g
        ok = g["voice"] and g["grounded"] and g["register"]
        lint_note = "" if g["lint_passed"] else f" lint:{g['lint_violations']}"
        print(f"{'PASS' if ok else 'FAIL'}  {row['case_id']}: voice={g['voice']} "
              f"grounded={g['grounded']} register={g['register']}{lint_note} | {g['worst_problem']}")

    out = Path(args.results).with_suffix(".judge.json")
    out.write_text(json.dumps(graded, indent=2))
    n = len(graded)
    if n:
        for axis in ("voice", "grounded", "register"):
            print(f"{axis}: {sum(1 for g in graded.values() if g[axis])}/{n}")
    print(f"Wrote {out}")

    if args.calibrate:
        labels_path = ROOT / args.labels
        if not labels_path.exists():
            print("No results/human_labels.json yet - hand-label some drafts first.")
            return
        human = json.loads(labels_path.read_text())
        common = [cid for cid in graded if cid in human]
        if not common:
            print("No overlapping case ids between judge output and human labels.")
            return
        print(f"\nCalibration vs {len(common)} blind human labels "
              f"(rubric v2, {args.samples}-sample consensus):")
        for axis in ("voice", "grounded", "register"):
            agree = sum(1 for cid in common if graded[cid][axis] == human[cid].get(axis))
            print(f"  {axis}: {agree}/{len(common)} ({agree / len(common):.0%})")
        disagreements = [(cid, axis) for cid in common for axis in ("voice", "grounded", "register")
                         if graded[cid][axis] != human[cid].get(axis)]
        if disagreements:
            print(f"  disagreements: {disagreements}")


if __name__ == "__main__":
    main()
