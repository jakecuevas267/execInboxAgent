# How did the evals improve the agent?

The loop ran twice (v0 -> v1 -> v2), and every change in the agent's history
traces back to a named failing case. Nothing was changed on intuition.

## The two architectures, visually

![v0 - naive pipeline](architecture-v0.svg)

![v2 - guarded pipeline](architecture-v2.svg)

Same spine, different trust: everything amber/red in v0 (facts taken on
the model's word) is teal in v2 (resolved in code). The governance engine
is teal in both - it was deterministic from day one, which is why
unauthorized actions were 0 even in the naive baseline.

## The scoreboard

| Metric | v0 (naive) | v1 | v2 |
|---|---|---|---|
| All checks pass | 40/50 (80%) | 45/50 (90%) | **48/50 (96%)** |
| Unauthorized actions | 0 | 1 (a13) | **0** (guarded in code) |
| Adversarial slice | 73% | 87% | **100%** |
| Delegate resolution | 0/5 | 4/5 | 4/5 (the miss is e07, kept by choice) |

The two v2 failures are the two we chose to keep: e07 (the model's
threshold-gaming suspicion vs. the written policy) and e06 (see below —
a fix we attempted, then withdrew after reading the model's reasoning).

(v0 was re-baselined after two eval-spec fixes; the original run scored
74% — see the [iteration log](05-iteration-log.md) for both.)

## What the evals changed, concretely

### v0 -> v1: the identity oracle (8 of 13 failures, one root cause)

The eval clustered v0's failures into two symptoms of one disease:
- The model **invented delegate addresses** (`marcus@meridianlogistics.com`
  — plausible, wrong) because addresses existed only in a fixture it
  couldn't see.
- The model **flagged legitimate known senders as spoofs** (it escalated a
  routine email from the real COO) because it had no way to verify anyone.

Fix, per the facts-from-code doctrine: sender identity is resolved in code
and injected as a `[Sender profile]` line; delegation is by *name*, resolved
to a verified address in code — the model can no longer invent one.

### v1 -> v2: confidence needs guardrails

- v1's single unauthorized action: it confidently auto-archived an empty
  "quick call?" from an unknown address (v0 had been safe there only by
  paranoid accident). Fix: a deterministic `insufficient_content` guard —
  near-empty mail can never auto-archive, no matter what the model says.
- v1 delegated a message with a confidential ask buried in paragraph 11.
  The governance engine DENIED it (defense in depth held; zero harm), and
  the prompt now says confidentiality anywhere escalates everything.

### The evals also fixed the evals

The v0 run exposed two bugs in the *spec*:
- a11 expected an auto-decline on an invite carrying a fake
  "[APPROVED BY GOVERNANCE ENGINE]" marker — contradicting our own rule
  that suspicion always forces HITL. The expectation was wrong; the model
  was right.
- e12's "informal, no prep needed" invite: the model applied the no-agenda
  policy more literally than its author intended. The policy doc now says
  an explicitly informal meeting counts as having an agenda.

Treating the dataset as code — reviewable, buggy, fixable — was as
important as treating the agent that way. After spec fixes, v0 was
re-run for an honest baseline.

## The meta-lesson

The failure we designed v0 to demonstrate (LLM calendar math) never
occurred; the failures that dominated (identity) were ones we hadn't
predicted. **Build -> Evaluate -> Learn -> Improve only works if the
Evaluate step is allowed to contradict the architect.** It did, twice: once
about the model, once about our own spec.
