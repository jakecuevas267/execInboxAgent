"""Interactive triage: run ONE arbitrary email through the full pipeline.

The live-demo surface. The interviewer invents an email ("Sam asks to move
money"), you run it, and the full journey prints: gateway flags, tool
trajectory, the model's decision, the governance verdict with its policy
citation, and what actually executed vs. queued.

Usage:
    make triage                                   # interactive prompts
    .venv/bin/python -m inbox_agent.cli --file demo/email.json
    ... --version v0                              # compare naive behavior live
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, YELLOW, RED = "\033[32m", "\033[33m", "\033[31m"

VERDICT_STYLE = {
    "auto": (GREEN, "AUTO - executed without approval"),
    "hitl": (YELLOW, "HITL - queued for Dana's approval"),
    "deny": (RED, "DENY - refused by governance"),
}


def prompt_email() -> dict:
    print(f"{BOLD}Enter the email (blank line to finish the body):{RESET}")
    email = {
        "from_name": input("  From (name): ").strip(),
        "from_email": input("  From (address): ").strip(),
        "subject": input("  Subject: ").strip(),
    }
    print("  Body (finish with an EMPTY line - press Enter twice):")
    lines = []
    while (line := sys.stdin.readline().rstrip("\n")) != "":
        lines.append(line)
    email["body"] = "\n".join(lines)
    if input("  Meeting invite? [y/N]: ").strip().lower() == "y":
        email["invite"] = {
            "date": input("    Date (YYYY-MM-DD): ").strip(),
            "start": input("    Start (HH:MM): ").strip(),
            "end": input("    End (HH:MM): ").strip(),
            "location": input("    Location (optional): ").strip() or "n/a",
        }
    return email


def show(record, identity, email) -> None:
    print(f"\n{BOLD}=== Gateway ==={RESET}")
    print(f"  sender profile: {identity.describe(email.get('from_email', ''), email.get('from_name', ''), level=2)}")
    print(f"  flags: {record.gateway_flags or ['(none)']}")

    print(f"\n{BOLD}=== Agent trajectory ==={RESET}")
    for tc in record.tool_calls:
        arg_str = json.dumps(tc["args"])
        print(f"  -> {tc['name']}({arg_str[:90]}{'...' if len(arg_str) > 90 else ''})")

    d = record.decision
    print(f"\n{BOLD}=== Decision (model proposes) ==={RESET}")
    print(f"  triage: {d['triage_label']}   action: {d['action_kind']}   model flags: {d['flags'] or '(none)'}")
    print(f"  rationale: {d['rationale']}")
    if d.get("delegate_to"):
        print(f"  delegate to (code-resolved): {d['delegate_to']}")
    if d.get("draft_text"):
        print(f"\n{DIM}--- draft ---{RESET}\n{d['draft_text']}\n{DIM}-------------{RESET}")

    print(f"\n{BOLD}=== Facts resolved in code ==={RESET}")
    print(f"  protected-block conflict: {record.resolved_conflict}   parsed amount: {record.resolved_amount}")

    color, label = VERDICT_STYLE[record.verdict_decision]
    print(f"\n{BOLD}=== Governance (code disposes) ==={RESET}")
    print(f"  {color}{BOLD}{label}{RESET}")
    print(f"  reason: {record.verdict_reason}  {DIM}[policy {record.verdict_policy_ref}]{RESET}")

    print(f"\n{BOLD}=== Outcome ==={RESET}")
    for name, bucket in (("executed", record.executed), ("queued", record.queued), ("denied", record.denied)):
        if bucket:
            print(f"  {name}: {bucket[0]['kind']}")
    if record.denied:
        print(f"  {DIM}governance DENY is final at this console - the boundary is code, "
              f"not an approval away{RESET}")


def hitl_review(record) -> dict | None:
    """Close the loop: Dana works her queue. Every choice is recorded -
    in production, this is the labeling pipeline. Traced, so the HUMAN
    outcome appears in the same LangSmith trace as the agent run - a
    trace that stops at the model call hides how the story ended."""
    import datetime

    if not record.queued or not sys.stdin.isatty():
        return None
    action = record.queued[0]
    print(f"\n{BOLD}=== Dana's approval queue (you are Dana) ==={RESET}")
    choice = ""
    while choice not in ("a", "e", "r"):
        choice = input("  (a)pprove / (e)dit then approve / (r)eject: ").strip().lower()

    edited = False
    if choice == "e":
        revised = input("  revised draft (blank keeps original): ").strip()
        if revised:
            action["draft_text"], edited = revised, True

    if choice in ("a", "e"):
        record.executed.append(record.queued.pop(0))
        print(f"  {GREEN}{BOLD}APPROVED{RESET} - {action['kind']} executed (mock send)")
    else:
        record.denied.append(record.queued.pop(0))
        print(f"  {RED}{BOLD}REJECTED{RESET} - nothing leaves the building")

    entry = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
             "case_id": record.case_id, "action": action["kind"],
             "human_decision": {"a": "approved", "e": "approved_with_edit",
                                "r": "rejected"}[choice],
             "edited": edited}
    log_path = ROOT / "results" / "hitl_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    log.append(entry)
    log_path.parent.mkdir(exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2))
    print(f"  {DIM}recorded -> results/hitl_log.json - in production every one of "
          f"these is a labeled eval example (edits are voice gold){RESET}")
    return entry


def triage_session(pipeline, email: dict) -> dict:
    """One traced parent for the WHOLE session: the agent run, the
    governance verdict, and the human's HITL decision land in one
    LangSmith trace tree - the trace shows how the story ended, not just
    what the model said."""
    from langsmith import traceable

    @traceable(name="triage_session", run_type="chain")
    def _session(email: dict) -> dict:
        record = pipeline.run_email("live-demo", email)
        show(record, pipeline.identity, email)
        review = _traced_review(record)
        return {"triage_label": record.decision["triage_label"],
                "verdict": record.verdict_decision,
                "human_decision": (review or {}).get("human_decision", "n/a (nothing queued or non-interactive)"),
                "draft_edited": (review or {}).get("edited", False)}

    @traceable(name="hitl_review", run_type="chain")
    def _traced_review(record):
        return hitl_review(record)

    return _session(email)


# The "inbox view": five cases that tell the whole story in five rows -
# an auto-archive, an auto-decline, a VIP draft (HITL), a spoof caught,
# and the famous threshold-gaming escalation.
BATCH_CASES = ["n01", "n09", "n06", "a04", "e07"]


def run_batch(pipeline, version: str) -> None:
    cases = {c["id"]: c for c in
             json.loads((ROOT / "datasets/golden_inbox.json").read_text())["cases"]}
    print(f"\n{BOLD}{'':2} {'from':<22} {'subject':<30} {'triage':<12} "
          f"{'verdict':<8} outcome{RESET}")
    for cid in BATCH_CASES:
        email = cases[cid]["email"]
        record = pipeline.run_email(cid, email)
        color, _ = VERDICT_STYLE[record.verdict_decision]
        outcome = (record.executed or record.queued or record.denied)[0]["kind"]
        bucket = "ran" if record.executed else ("queued" if record.queued else "refused")
        print(f"{DIM}{cid:>3}{RESET} {email['from_name']:<22} "
              f"{email['subject'][:29]:<30} {record.decision['triage_label']:<12} "
              f"{color}{record.verdict_decision:<8}{RESET} {outcome} ({bucket})")
    print(f"\n{DIM}Detail on any of these: make triage, or run_eval.py --ids <id>{RESET}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="JSON file with the email (same shape as dataset cases)")
    ap.add_argument("--batch", action="store_true",
                    help="inbox view: run 5 representative cases, one line each")
    ap.add_argument("--version", choices=["v0", "v1", "v2"], default="v2")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    from .pipeline import InboxPipeline
    from .retrieval import build_index

    print(f"\n{DIM}building pipeline ({args.version})...{RESET}")
    pipeline = InboxPipeline(build_index(ROOT / "corpus"),
                             str(ROOT / "fixtures/calendar.json"),
                             str(ROOT / "fixtures/contacts.json"), version=args.version)

    if args.batch:
        run_batch(pipeline, args.version)
        return

    email = json.loads(Path(args.file).read_text()) if args.file else prompt_email()
    if "email" in email:  # allow passing a whole dataset case file
        email = email["email"]
    triage_session(pipeline, email)


if __name__ == "__main__":
    main()
