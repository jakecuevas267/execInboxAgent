"""Mirror the golden-set eval into LangSmith as datasets + experiments.

The local runner (run_eval.py) stays the source of truth - deterministic,
CI-able, vendor-independent. This module is the presentation/comparison
layer: it uploads the golden set as a LangSmith dataset and replays a
version through `langsmith.evaluate()`, so each version becomes a named
experiment with the same seven deterministic checks attached as feedback
scores and a trace per example.

Usage:
    python evals/langsmith_sync.py --upload-only     # create/verify dataset (free)
    python evals/langsmith_sync.py --version v0      # run v0 as an experiment ($)
    python evals/langsmith_sync.py --version v2      # run v2 as an experiment ($)

Compare experiments side by side in LangSmith: Datasets & Experiments ->
exec-inbox-agent-golden.
"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from langsmith import Client, evaluate  # noqa: E402

from run_eval import check_case  # noqa: E402  (same checks, one definition)

DATASET_NAME = "exec-inbox-agent-golden"


def load_cases() -> list[dict]:
    return json.loads((ROOT / "datasets/golden_inbox.json").read_text())["cases"]


def ensure_dataset(client: Client) -> str:
    """Create the dataset if needed; idempotent. Returns dataset name."""
    cases = load_cases()
    if client.has_dataset(dataset_name=DATASET_NAME):
        existing = list(client.list_examples(dataset_name=DATASET_NAME))
        if len(existing) == len(cases):
            print(f"Dataset '{DATASET_NAME}' already has {len(existing)} examples - leaving as is.")
            return DATASET_NAME
        print(f"Dataset '{DATASET_NAME}' has {len(existing)} examples, expected {len(cases)} - recreating.")
        client.delete_dataset(dataset_name=DATASET_NAME)

    ds = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="50 golden inbox cases (20 normal / 15 edge / 15 adversarial) "
                    "with expected triage outcomes. Source of truth: datasets/golden_inbox.json",
    )
    client.create_examples(
        dataset_id=ds.id,
        inputs=[{"case_id": c["id"], "email": c["email"]} for c in cases],
        outputs=[{"expected": c["expected"]} for c in cases],
        metadata=[c["tags"] for c in cases],
    )
    print(f"Created dataset '{DATASET_NAME}' with {len(cases)} examples.")
    return DATASET_NAME


def make_target(version: str):
    """Build the pipeline once; each call triages one dataset example."""
    from inbox_agent.pipeline import InboxPipeline
    from inbox_agent.retrieval import build_index

    pipeline = InboxPipeline(
        build_index(ROOT / "corpus"),
        str(ROOT / "fixtures/calendar.json"),
        str(ROOT / "fixtures/contacts.json"),
        version=version,
    )

    def target(inputs: dict) -> dict:
        record = pipeline.run_email(inputs["case_id"], inputs["email"])
        return record.to_dict()

    return target


def deterministic_checks(run, example) -> dict:
    """One evaluator emitting all seven checks (+all_pass) as feedback."""
    record = SimpleNamespace(**run.outputs)  # RunRecord.to_dict() round-trip
    case = {"expected": example.outputs["expected"]}
    checks = check_case(case, record)
    return {"results": [{"key": k, "score": bool(v)} for k, v in checks.items()]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=["v0", "v1", "v2"])
    ap.add_argument("--upload-only", action="store_true")
    args = ap.parse_args()
    if not args.upload_only and not args.version:
        ap.error("pass --upload-only or --version vX")

    client = Client()
    ensure_dataset(client)
    if args.upload_only:
        print("Upload-only: no experiment run. Inspect the dataset in LangSmith, "
              "then run with --version v0 / --version v2.")
        return

    import os
    result = evaluate(
        make_target(args.version),
        data=DATASET_NAME,
        evaluators=[deterministic_checks],
        experiment_prefix=f"golden-{args.version}",
        metadata={"version": args.version,
                  "agent_model": os.environ.get("AGENT_MODEL", "claude-opus-5")},
        max_concurrency=4,
        client=client,
    )
    print(f"\nExperiment complete: {result.experiment_name}")


if __name__ == "__main__":
    main()
