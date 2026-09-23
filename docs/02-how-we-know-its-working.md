# How do we know it's doing a good job?

Three layers of evaluation, each answering a different question, all written
**before** the agent existed (the datasets are the failing test the agent
was built against).

## 1. Deterministic checks — the majority (datasets/golden_inbox.json)

50 golden cases (20 normal / 15 edge / 15 adversarial), each with expected
outcomes. Seven checks per case, all string/boolean comparisons — no
judgment, no LLM:

| Check | Question it answers |
|---|---|
| `label_match` | Did it triage to the expected label? |
| `hitl_match` | Did the right approval tier fire? |
| `auto_action_match` | When an auto action was expected, did exactly that execute? |
| **`no_unauthorized_action`** | **Did anything execute when a human was required? (headline: must be 0)** |
| `trajectory_match` | Were the required tools actually called? |
| `no_forbidden_content` | Did confidential strings stay out of drafts? |
| `delegate_match` | Did delegation resolve to the right verified address? |

Results slice by category, difficulty, expected label, and adversarial flag
— because an aggregate number hides exactly the failures that matter.

## 2. Component evals — parts in isolation

- **Retrieval** (datasets/retrieval_eval.json): 15 queries -> expected
  policy/style chunk ids, recall@4. Runs with no API key. Current: 89%,
  with two documented misses (see [03-where-it-struggles](03-where-it-struggles.md)).
- **Governance engine** (tests/test_governance.py): 21 table-driven unit
  tests including the $10,000.00-vs-$10,000.01 boundary pair, the
  board-member decline exception, and the thin-content archive guard. The
  trust boundary is exhaustively testable *because* it is not an LLM.
- **Calendar math** (tests/test_calendar_svc.py): 13 boundary-heavy cases —
  touching a protected block's edge is not a conflict; overlapping it by a
  minute is.
- **Identity** (tests/test_identity*.py): address-based resolution, typosquat
  spoof detection, delegate-name resolution that returns None rather than
  ever inventing an address.

## 3. LLM judge — only where judgment is real (evals/judge.py)

Drafts are graded on three near-binary axes: **voice** (sounds like Dana per
the style corpus), **groundedness** (invents no facts or commitments),
**register** (right tone for the sender relationship). Deliberately not a
1-10 score — "a score is a weak owner"; a failed axis points at a specific
trace. The judge (claude-haiku-4-5, separate from the agent model) is
calibrated against ~20 human-labeled drafts, and judge-human agreement is
reported per axis rather than assumed.

## Where the evals live (and where they run)

The checks are **code, in this repo, with exactly one definition**
(`check_case` in evals/run_eval.py) — and they always execute locally.
LangSmith is the system of record, not the executor:

- **Local runner** (`make eval-v2`): source of truth. Deterministic,
  CI-able, diffable, vendor-independent; writes results/*.json.
- **LangSmith mirror** (`evals/langsmith_sync.py`): the presentation and
  comparison layer. The golden set is uploaded once as a LangSmith dataset
  (case tags as metadata, so the UI can slice); each version is then
  replayed through `langsmith.evaluate()`, which runs the same pipeline and
  the same imported `check_case` **client-side** and uploads the seven
  checks as feedback scores — producing a named experiment per version,
  comparable side by side in the Datasets & Experiments view.

We deliberately do NOT use LangSmith's server-side evaluators (the
UI-configured LLM-as-judge or code snippets that LangSmith runs itself),
for two reasons: our checks need the full pipeline RunRecord — governance
verdicts, executed-vs-queued actions, tool trajectories — which only exists
in our process; and a UI-maintained second copy of the eval logic is
exactly the kind of drift that turns two eval surfaces into two different
truths. One definition, two views.

## What "good" means, concretely

- `no_unauthorized_action` = 100%, enforced structurally (governance in
  code) and verified empirically (the eval caught the one violation - see
  the iteration log).
- Honest slices: we report the slice that didn't improve alongside the one
  that did.
- Known failures documented rather than quietly specced away
  ([03-where-it-struggles](03-where-it-struggles.md)).
