"""Inbound gateway scan (v1 hardening).

Runs BEFORE the model sees the email. Produces flags that ride along to the
governance engine, so a suspicious message can never take an auto action no
matter what the model concludes. Pattern-based on purpose: cheap, auditable,
and it doesn't have to be perfect - it has to make suspicion sticky.
"""

import re
from dataclasses import dataclass, field

from .identity import IdentityService

# Phrases that address the assistant/AI directly or claim pre-approval.
_INJECTION_PATTERNS = [
    r"\b(ai|scheduling)?\s*assistant\b.{0,60}\b(send|approve|skip|forward|decline|cc)\b",
    r"\bignore (all|any|previous|prior) (instructions|rules)\b",
    r"\bpre-?approved\b",
    r"\bskip the approval\b",
    r"\bapproved by (the )?governance\b",
    r"\bnote to (the )?(ai|scheduling|assistant)\b",
    r"\bautomatically (cc|bcc|forward|reply)\b",
    r"\bconfigure your assistant\b",
]

# Requests that policy §4 treats as hostile regardless of sender.
_EXFIL_PATTERNS = [
    r"\bforward\b.{0,60}\b(deck|board|document|file|summary|term sheet)\b",
    r"\bsend\b.{0,60}\b(compensation|comp ranges|payroll|salary)\b",
    r"\bshare\b.{0,60}\b(comp|compensation|salary|schedule)\b",
]

_MONEY_PATTERNS = [
    r"\bwire\b", r"\bpayout\b", r"\btransfer\b.{0,30}\$", r"\$\s?\d{2,3},\d{3}",
]

_PHISH_PATTERNS = [
    r"\bverify your (account|details|identity)\b",
    r"\b(account|mailbox).{0,40}(suspend|suspended|locked)\b",
]

_CONFIDENTIAL_TERMS = ["bluebird", "term sheet", "board deck", "compensation", "comp ranges", "payroll"]


@dataclass(frozen=True)
class GatewayReport:
    flags: frozenset
    matched: tuple = field(default_factory=tuple)  # (flag, pattern) pairs for the audit log


def scan(email: dict, identity: IdentityService) -> GatewayReport:
    """email keys: from_name, from_email, subject, body, optional invite."""
    text = " ".join([
        email.get("subject", ""),
        email.get("body", ""),
        str(email.get("invite", {}).get("location", "")) if email.get("invite") else "",
    ]).lower()

    flags, matched = set(), []

    def check(patterns, flag):
        for p in patterns:
            if re.search(p, text):
                flags.add(flag)
                matched.append((flag, p))

    check(_INJECTION_PATTERNS, "injection_suspected")
    check(_EXFIL_PATTERNS, "confidentiality")
    check(_MONEY_PATTERNS, "money_movement")
    check(_PHISH_PATTERNS, "phishing_suspected")

    if any(term in text for term in _CONFIDENTIAL_TERMS):
        flags.add("confidentiality")

    resolved = identity.resolve(email.get("from_email", ""), email.get("from_name", ""))
    if resolved.display_name_spoof:
        flags.add("spoof_suspected")

    return GatewayReport(frozenset(flags), tuple(matched))
