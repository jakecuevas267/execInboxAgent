# Self-audit against the brief

Mapping the take-home's "What We'd Like to See" and "Nice Extras" to what's
built. Honest status per item; gaps are named, not hidden — consciously
skipped items are marked as choices, with reasons.

## What We'd Like to See

| Ask | Status | Where |
|---|---|---|
| Working agent, ≥1 useful tool, retrieval step (RAG) | ✅ | LangGraph ReAct agent; tools `search_context` (BM25 RAG over policy/style corpus), `calendar_lookup`, `submit_decision`. src/inbox_agent/agent.py |
| ≥1 evaluation dataset with expected outcomes | ✅ (3 datasets) | 50-case golden set + 15-query retrieval set (datasets/) + 22-row governance table suite (tests/test_governance.py) |
| Deterministic checks where they make sense | ✅ (they carry the eval) | 7 checks/case incl. headline `no_unauthorized_action`; evals/run_eval.py `check_case` |
| LLM judge where human-like judgment is useful | ✅ | Voice/groundedness/register on drafts only — the genuinely judgment-shaped part. evals/judge.py |
| Traces we can look through | ✅ | LangSmith project `exec-inbox-agent`; decision is a tool-call span. Star traces: a12 (governance DENY), a13 (guard catch) |
| Before-and-after evaluation results | ✅ | v0 80% → v1 90% → v2 96%, sliced; results/*.json; docs/04 |
| Failures, tradeoffs, things we're unsure about | ✅ (a strength) | docs/03 + docs/05: e07 kept failing on purpose, e06 fix withdrawn, uncalibrated-judge voice cluster, BM25 synonym misses |
| How we'd evaluate in production | ✅ | README §Evaluating in production: HITL queue as labeling pipeline, CI release gate, sampled online review, drift on decision mix |

## Nice Extras

| Extra | Status | Notes |
|---|---|---|
| Judge calibration vs human labels | ✅ | 13 drafts labeled blind; agreement voice 69% / grounded 92% / register 100%. Calibration priced the axes: register gateable, grounded needs consensus sampling (judge self-inconsistent on e13), voice demoted to directional. docs/05 Iteration 5 |
| Results in useful slices | ✅ | category / difficulty / expected-label / adversarial, printed every run |
| Evaluating tool calls / trajectories | ✅ | `trajectory_match` (must_call ⊆ called); executor gating verified via executed/queued/denied lists |
| Intentionally tricky examples | ✅ | 15 adversarial cases: injection in invite location, typosquat spoofs, CEO-fraud wire, buried confidential ask, fake governance-approval marker |
| Trying an online evaluation | 🟠 designed, not run | Production doc describes it; nothing streams live traffic (no real inbox exists). Honest framing: "designed, and here's what I'd wire first" |
| PII handling or guardrails | ✅ guardrails / 🟡 PII | Gateway scan (injection/exfil/spoof/thin-content), governance DENY tier, `reply_must_not_contain` checks, confidentiality escalation. No PII *redaction* layer (e.g. scrubbing before traces export) — worth one honest sentence |
| Streaming output | ❌ skipped deliberately | Batch triage has no user waiting on tokens; streaming would be decoration. Say so if asked |
| Easy setup script / Makefile / Docker | ✅ Makefile / ❌ Docker | make setup/test/demo/eval-*/judge; no Docker — venv + fixtures need nothing containerized |

## The two sentences that matter

"Perfect scores aren't the goal - we'd rather see honest failures and what
you learned from them" is the rubric line this submission is built around:
two failures kept by choice, one fix withdrawn with reasons, a judge finding
deliberately left unremediated pending calibration, and an iteration log
where the eval contradicts the architect twice.

## Gaps ranked by close-cost

1. **Judge calibration labels** — 20 min of Jake's time, closes a Nice Extra. Do it.
2. **LangSmith experiments** — makes "before-and-after results" clickable
   in their own tool. Built: golden set uploaded as a dataset; experiments
   run client-side via `langsmith.evaluate()` with the same imported
   `check_case` (no server-side evaluators — one definition of the checks,
   see docs/02 §Where the evals live). Pending: the v0 + v2 experiment runs.
3. **PII redaction sentence** — add one honest line to docs/03. Free.
4. Streaming / Docker / live online eval — consciously skipped; defensible.
