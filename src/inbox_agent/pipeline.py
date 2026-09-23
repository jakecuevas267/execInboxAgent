"""End-to-end pipeline for one email:

    (v1: gateway scan) -> agent -> facts resolved in code -> governance
    -> executor (mock) -> audit record

The model proposes; code disposes. Facts that gate autonomy (calendar
conflicts, amounts, sender identity, suspicion flags) are resolved
deterministically in v1; v0 leans on the model for them - that gap is the
before/after eval story.
"""

import re
from dataclasses import asdict, dataclass, field

from . import gateway as gateway_mod
from .agent import Decision, build_agent, extract_decision
from .calendar_svc import CalendarService
from .governance import Decision as GovDecision
from .governance import ProposedAction, Sender, Verdict, govern
from .identity import IdentityService
from .retrieval import BM25Index

_AMOUNT = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


def parse_amount(text: str) -> float | None:
    amounts = [float(m.replace(",", "")) for m in _AMOUNT.findall(text)]
    return max(amounts) if amounts else None


@dataclass
class RunRecord:
    case_id: str
    version: str
    decision: dict
    gateway_flags: list
    resolved_conflict: bool
    resolved_amount: float | None
    verdict_decision: str
    verdict_reason: str
    verdict_policy_ref: str
    executed: list = field(default_factory=list)   # actions that actually ran (auto tier)
    queued: list = field(default_factory=list)     # actions waiting for Dana (hitl tier)
    denied: list = field(default_factory=list)     # actions refused (deny tier)
    tool_calls: list = field(default_factory=list)
    error: str | None = None

    def to_dict(self):
        return asdict(self)


class InboxPipeline:
    def __init__(self, index: BM25Index, calendar_path: str, contacts_path: str, version: str = "v1"):
        self.version = version
        self.calendar = CalendarService(calendar_path)
        self.identity = IdentityService(contacts_path)
        self.agent = build_agent(index, self.calendar, version)

    def run_email(self, case_id: str, email: dict) -> RunRecord:
        # 1. Gateway scan (hardened pipeline only).
        level = {"v0": 0, "v1": 1}.get(self.version, 2)
        gw_flags: frozenset = frozenset()
        if level >= 1:
            gw_flags = gateway_mod.scan(email, self.identity, level=level).flags

        # 2. The reasoning node. In v1 the system-resolved sender profile is
        # injected ahead of the model so it never guesses about identity.
        content = render_email(email)
        if level >= 1:
            profile = self.identity.describe(email.get('from_email', ''), email.get('from_name', ''), level=level)
            content = f"[Sender profile] {profile}\n{content}"
        result = self.agent.invoke({"messages": [{"role": "user", "content": content}]})
        decision: Decision = extract_decision(result)

        # v1: the model delegates by NAME; code resolves it to a verified
        # address (v0 hallucinated addresses). Unresolvable delegate -> None,
        # which the eval will catch rather than an invented domain slipping by.
        if self.version != "v0" and decision.delegate_to:
            decision.delegate_to = self.identity.resolve_delegate(decision.delegate_to)
        tool_calls = [
            {"name": tc["name"], "args": tc["args"]}
            for m in result["messages"]
            for tc in (getattr(m, "tool_calls", None) or [])
        ]

        # 3. Facts resolved in code (v1) or taken from the model (v0).
        invite = email.get("invite")
        if self.version == "v0":
            conflict = decision.protected_block_conflict
        else:
            conflict = bool(invite) and self.calendar.check_invite(
                invite["date"], invite["start"], invite["end"]).conflict
        amount = parse_amount(f"{email.get('subject', '')} {email.get('body', '')}")

        sender_r = self.identity.resolve(email.get("from_email", ""), email.get("from_name", ""))
        sender = Sender(email=sender_r.email, known=sender_r.known, internal=sender_r.internal,
                        exec_team=sender_r.exec_team, vip=sender_r.vip, board=sender_r.board)

        flags = frozenset(decision.flags) | gw_flags

        # 4. Governance.
        verdict: Verdict = govern(ProposedAction(
            kind=decision.action_kind, sender=sender, flags=flags,
            protected_block_conflict=conflict, amount=amount,
        ))

        # 5. Executor (mock): only AUTO verdicts execute; everything else queues.
        record = RunRecord(
            case_id=case_id, version=self.version, decision=decision.model_dump(),
            gateway_flags=sorted(gw_flags), resolved_conflict=conflict, resolved_amount=amount,
            verdict_decision=verdict.decision.value, verdict_reason=verdict.reason,
            verdict_policy_ref=verdict.policy_ref, tool_calls=tool_calls,
        )
        action = {"kind": decision.action_kind, "draft_text": decision.draft_text,
                  "delegate_to": decision.delegate_to}
        if verdict.decision == GovDecision.AUTO:
            record.executed.append(action)
        elif verdict.decision == GovDecision.HITL:
            record.queued.append(action)
        else:
            record.denied.append(action)
        return record


def render_email(email: dict) -> str:
    lines = [
        f"From: {email.get('from_name', '')} <{email.get('from_email', '')}>",
        f"Subject: {email.get('subject', '')}",
        "",
        email.get("body", ""),
    ]
    invite = email.get("invite")
    if invite:
        lines += ["", f"[Meeting invite] date={invite['date']} start={invite['start']} "
                      f"end={invite['end']} location={invite.get('location', 'n/a')}"]
    return "\n".join(lines)
