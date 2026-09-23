"""LLM judge for draft quality - the genuinely judgment-shaped part.

Grades only cases that produced a draft. Three binary-ish rubric axes
(voice, groundedness, register), not a 1-10 score: coarse rubrics are
defensible and calibratable. Judge model is cheap and separate from the
agent model on purpose.

Usage:
    python evals/judge.py --results results/v1.json
Writes results/<name>.judge.json.

Calibration: hand-label ~20 drafts in results/human_labels.json as
{"<case_id>": {"voice": true/false, ...}} then run with --calibrate to
report judge-human agreement.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from langchain_anthropic import ChatAnthropic  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

JUDGE_MODEL = "claude-haiku-4-5"

STYLE = (ROOT / "corpus/style_examples.md").read_text()


class DraftGrade(BaseModel):
    voice: bool = Field(..., description="Sounds like Dana per the style examples: warm, brief, <=2 short paragraphs, first names, '- Dana' close, no corporate filler, no signature block")
    grounded: bool = Field(..., description="Makes no commitments, facts, or offers not supported by the email/context; invents nothing")
    register: bool = Field(..., description="Tone is appropriate for the sender relationship (internal peer vs external vs VIP)")
    worst_problem: str = Field(..., description="One sentence: the single biggest issue, or 'none'")


PROMPT = """You are grading a draft email written by an assistant on behalf of \
Dana Whitfield (CEO). Grade STRICTLY against the rubric fields.

Dana's real style examples:
{style}

The inbound email:
{email}

The assistant's draft:
{draft}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--calibrate", action="store_true")
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
        grade: DraftGrade = judge.invoke(PROMPT.format(style=STYLE, email=email_text, draft=draft))
        graded[row["case_id"]] = grade.model_dump()
        ok = grade.voice and grade.grounded and grade.register
        print(f"{'PASS' if ok else 'FAIL'}  {row['case_id']}: voice={grade.voice} "
              f"grounded={grade.grounded} register={grade.register} | {grade.worst_problem}")

    out = Path(args.results).with_suffix(".judge.json")
    out.write_text(json.dumps(graded, indent=2))
    n = len(graded)
    if n:
        for axis in ("voice", "grounded", "register"):
            print(f"{axis}: {sum(1 for g in graded.values() if g[axis])}/{n}")
    print(f"Wrote {out}")

    if args.calibrate:
        labels_path = ROOT / "results/human_labels.json"
        if not labels_path.exists():
            print("No results/human_labels.json yet - hand-label some drafts first.")
            return
        human = json.loads(labels_path.read_text())
        common = [cid for cid in graded if cid in human]
        if not common:
            print("No overlapping case ids between judge output and human labels.")
            return
        for axis in ("voice", "grounded", "register"):
            agree = sum(1 for cid in common if graded[cid][axis] == human[cid].get(axis))
            print(f"judge-human agreement on {axis}: {agree}/{len(common)} ({agree / len(common):.0%})")


if __name__ == "__main__":
    main()
