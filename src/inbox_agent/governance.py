"""Deterministic governance engine.

The trust boundary of the system. Takes a proposed action (from the LLM
agent) plus resolved facts (from code, never from the model) and decides:

    AUTO  - execute without approval
    HITL  - queue for Dana's approval
    DENY  - refuse and escalate (the action is never available)

This module has no LLM calls and no I/O, so it is exhaustively unit-testable.
Policy references map to sections of corpus/exec_preferences.md.
"""

from dataclasses import dataclass, field
from enum import Enum

DELEGATION_AMOUNT_LIMIT = 10_000  # policy §3: strictly over this escalates

# Flags that mean "something is suspicious"; suspicious work never runs auto.
SUSPICION_FLAGS = frozenset({
    "injection_suspected",
    "spoof_suspected",
    "phishing_suspected",
    "confidentiality",
    "money_movement",
})

# Action kinds that exist in the system. Anything else is out of scope and
# denied outright (policy §6 "never" tier).
KNOWN_KINDS = frozenset({
    "archive",
    "send_reply",
    "decline_meeting",
    "accept_meeting",
    "delegate",
    "escalate",
})


class Decision(str, Enum):
    AUTO = "auto"
    HITL = "hitl"
    DENY = "deny"


@dataclass(frozen=True)
class Sender:
    email: str
    known: bool = False
    internal: bool = False
    exec_team: bool = False
    vip: bool = False
    board: bool = False


@dataclass(frozen=True)
class ProposedAction:
    kind: str
    sender: Sender
    flags: frozenset = field(default_factory=frozenset)
    # Resolved by calendar code, never by the model:
    protected_block_conflict: bool = False
    # Resolved by parsing code for invoices/amounts:
    amount: float | None = None


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    reason: str
    policy_ref: str


def govern(action: ProposedAction) -> Verdict:
    flags = frozenset(action.flags)
    suspicious = bool(flags & SUSPICION_FLAGS)

    if action.kind not in KNOWN_KINDS:
        return Verdict(Decision.DENY, f"unknown action kind '{action.kind}' is out of scope", "§6-never")

    if action.kind == "escalate":
        return Verdict(Decision.HITL, "escalation goes to Dana by definition", "§2")

    # Confidential material must never leave in an outbound draft (§4).
    if action.kind in ("send_reply", "delegate") and "confidentiality" in flags:
        return Verdict(Decision.DENY, "outbound content flagged confidential", "§4")

    if action.kind == "archive":
        if suspicious:
            return Verdict(Decision.HITL, "suspicious mail is surfaced, not silently archived", "§2")
        if "insufficient_content" in flags:
            return Verdict(Decision.HITL, "message too thin to classify stays human-visible", "§2")
        return Verdict(Decision.AUTO, "archive is in the auto tier", "§6-auto")

    if action.kind == "decline_meeting":
        if action.sender.board:
            return Verdict(Decision.HITL, "board members are never auto-declined", "§1")
        if suspicious:
            return Verdict(Decision.HITL, "suspicion flag present", "§6")
        if action.protected_block_conflict:
            return Verdict(Decision.AUTO, "true protected-block conflict, non-board sender", "§1/§6-auto")
        return Verdict(Decision.HITL, "declines without a protected-block conflict need approval", "§6-hitl")

    if action.kind == "delegate":
        if action.amount is not None and action.amount > DELEGATION_AMOUNT_LIMIT:
            return Verdict(Decision.DENY, f"amount {action.amount:.2f} over delegation limit; escalate to Dana", "§3")

    # Everything else that reached here (send_reply, accept_meeting,
    # delegate within limits) is outbound work: always approved by a human.
    return Verdict(Decision.HITL, "outbound action requires approval", "§6-hitl")
