# Planned next steps

The project is feature-complete for its purpose (an evaluated
trust-tiered agent with a documented iteration history). These are the
steps a continued engagement would take, in order, with the reasoning
for the sequence.

## 1. Tune drafting against the lint standard (licensed, not yet done)

The style lint fails a majority of current drafts (the filler habit:
"thanks for setting this up" etc.). Under rubric v1 tuning was
deliberately refused - iterating against an axis two honest readers
split on launders judge taste into fake progress. Rubric v2 changed
that: the standard is now defined, calibrated (voice 92%), and
mechanically checkable, so hill-climbing the drafting prompt against it
is legitimate. Approach: add the banned-phrase list and lead-with-the-
answer rule to the drafting section of the system prompt, re-run the
13-draft set, report lint pass-rate before/after. Cheap, high-signal.

## 2. Validate rubric v2.1 wording

The grounded rubric gained range-membership and weekday-resolution
wording after the judge lost all three adjudicated disputes (Discovery
O). That wording has not yet been through a run. Re-run the judge on the
current results and confirm the three former false-fails (n09, n10,
e05) now pass grounded without loosening the axis elsewhere.

## 3. Grounded consensus in production shape

3-sample majority voting exists in the harness. Before gating anything
on grounded, measure vote-split frequency across a larger draft set: if
splits are rare, 3 samples suffice; if common, the axis needs a sharper
rubric, not more votes.

## 4. The e07 policy conversation

The agent escalates invoices of exactly $10,000 from unverified senders
in every run - stable threshold-gaming suspicion the written policy
doesn't share. This is a decision for the policy owner: either amend §3
("at or near the threshold from unverified senders escalates") and flip
the eval expectation, or keep the policy and accept the standing eval
failure as a documented disagreement. Deliberately left open: it is a
conversation, not a commit.

## 5. Retrieval: the embeddings escape hatch

BM25's measured boundary is 89% recall@4 with both misses being synonym
gaps. The swap is one file behind the same search() interface. Trigger
condition: corpus growth beyond a handful of documents, or a downstream
failure actually caused by a lexical miss (none so far). At that point
retrieval becomes model-dependent and variable - and graduates to
LangSmith experiment tracking accordingly.

## 6. Production wiring (in dependency order)

1. GmailInbox / GmailSender per the connectors.py docstrings (OAuth with
   read/send on separate identities, watch + Pub/Sub, normalization,
   idempotency).
2. A real approval-queue UI (the CLI's approve/edit/reject loop and
   hitl_log.json define the data contract).
3. Durable state: Postgres behind the audit log and HITL queue.
4. Trace redaction before export once real mail flows (synthetic data
   made public traces safe; production data will not be).
5. Online evaluation per the README: the HITL queue as labeling
   pipeline, golden set as CI release gate, drift monitors on the
   decision mix.

## 7. Widening the slice (the north-star diagram)

Calendar actions beyond declines, then delegation handoffs (Slack), then
brief-prep - each added as a new evaluated vertical with its own golden
cases before any code, per the pattern this repo establishes. The
router stays data (triage_label) until an added surface genuinely
requires parallel work.

---

Parked deliberately. The eval harness is the asset: any of these steps
starts by writing its failing cases first.
