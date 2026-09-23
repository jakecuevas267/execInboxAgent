"""Component eval for the retrieval step: recall@k on chunk ids.

Runs with no API key - the retriever is deterministic. Expected ids match
by prefix (e.g. expected 'style_examples#example-5' matches the chunk
'style_examples#example-5-decline-with-alternative-protected-block').
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from inbox_agent.retrieval import build_index  # noqa: E402


def main():
    spec = json.loads((ROOT / "datasets/retrieval_eval.json").read_text())
    index = build_index(ROOT / "corpus")
    k = spec["k"]

    total_expected = total_hit = cases_full = 0
    for case in spec["cases"]:
        got = [c.chunk_id for c, _ in index.search(case["query"], k=k)]
        hits = [e for e in case["expected_chunks"]
                if any(g == e or g.startswith(e + "-") or g.startswith(e) for g in got)]
        total_expected += len(case["expected_chunks"])
        total_hit += len(hits)
        full = len(hits) == len(case["expected_chunks"])
        cases_full += full
        status = "PASS" if full else "MISS"
        print(f"{status}  {case['id']}: {case['query']!r}")
        if not full:
            missing = set(case["expected_chunks"]) - set(hits)
            print(f"      missing={sorted(missing)} got={got}")

    n = len(spec["cases"])
    print(f"\nrecall@{k}: {total_hit}/{total_expected} chunks "
          f"({total_hit / total_expected:.0%}); full-case: {cases_full}/{n}")


if __name__ == "__main__":
    main()
