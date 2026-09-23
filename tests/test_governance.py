"""Table-driven unit suite for the governance engine.

The trust boundary is deterministic code, so it gets exhaustive tests.
Every row: (case name, proposed action, expected decision).
"""

import pytest

from inbox_agent.governance import (
    Decision,
    ProposedAction,
    Sender,
    Verdict,
    govern,
)

INTERNAL = Sender(email="marcus.rivera@meridianlog.com", known=True, internal=True, exec_team=True)
STAFF = Sender(email="leah.ortiz@meridianlog.com", known=True, internal=True)
EXTERNAL = Sender(email="sam.porter@freightwise.io", known=True)
VIP = Sender(email="jim.calloway@apexretail.com", known=True, vip=True)
BOARD = Sender(email="rchen@halcyonpartners.com", known=True, board=True)
UNKNOWN = Sender(email="nobody@example.com", known=False)

CASES = [
    # --- archive tier ----------------------------------------------------
    ("archive_clean_is_auto",
     ProposedAction("archive", UNKNOWN), Decision.AUTO),
    ("archive_with_phishing_flag_is_hitl",
     ProposedAction("archive", UNKNOWN, flags=frozenset({"phishing_suspected"})), Decision.HITL),
    ("archive_with_injection_flag_is_hitl",
     ProposedAction("archive", EXTERNAL, flags=frozenset({"injection_suspected"})), Decision.HITL),

    # --- outbound drafts are always approved ------------------------------
    ("send_reply_internal_is_hitl",
     ProposedAction("send_reply", INTERNAL), Decision.HITL),
    ("send_reply_external_is_hitl",
     ProposedAction("send_reply", EXTERNAL), Decision.HITL),
    ("send_reply_vip_is_hitl_not_auto",
     ProposedAction("send_reply", VIP), Decision.HITL),
    ("send_reply_confidential_is_denied",
     ProposedAction("send_reply", EXTERNAL, flags=frozenset({"confidentiality"})), Decision.DENY),

    # --- meeting declines --------------------------------------------------
    ("decline_true_conflict_nonboard_is_auto",
     ProposedAction("decline_meeting", EXTERNAL, protected_block_conflict=True), Decision.AUTO),
    ("decline_true_conflict_vip_is_still_auto_policy_tension",
     ProposedAction("decline_meeting", VIP, protected_block_conflict=True), Decision.AUTO),
    ("decline_board_member_is_never_auto",
     ProposedAction("decline_meeting", BOARD, protected_block_conflict=True), Decision.HITL),
    ("decline_without_conflict_is_hitl",
     ProposedAction("decline_meeting", EXTERNAL, protected_block_conflict=False), Decision.HITL),
    ("decline_conflict_but_suspicious_is_hitl",
     ProposedAction("decline_meeting", EXTERNAL, protected_block_conflict=True,
                    flags=frozenset({"injection_suspected"})), Decision.HITL),

    # --- accepting meetings ------------------------------------------------
    ("accept_meeting_is_hitl",
     ProposedAction("accept_meeting", INTERNAL), Decision.HITL),

    # --- delegation and the $10k boundary ---------------------------------
    ("delegate_no_amount_is_hitl",
     ProposedAction("delegate", EXTERNAL), Decision.HITL),
    ("delegate_at_exactly_10000_is_hitl_not_deny",
     ProposedAction("delegate", EXTERNAL, amount=10_000.00), Decision.HITL),
    ("delegate_at_10000_01_is_denied",
     ProposedAction("delegate", EXTERNAL, amount=10_000.01), Decision.DENY),
    ("delegate_confidential_is_denied",
     ProposedAction("delegate", STAFF, flags=frozenset({"confidentiality"})), Decision.DENY),

    # --- escalation and out-of-scope ---------------------------------------
    ("escalate_is_hitl",
     ProposedAction("escalate", UNKNOWN), Decision.HITL),
    ("wire_transfer_kind_is_denied",
     ProposedAction("wire_transfer", INTERNAL), Decision.DENY),
    ("delete_email_kind_is_denied",
     ProposedAction("delete_email", INTERNAL), Decision.DENY),
    ("forward_external_kind_is_denied",
     ProposedAction("forward_external", BOARD), Decision.DENY),
]


@pytest.mark.parametrize("name,action,expected", CASES, ids=[c[0] for c in CASES])
def test_governance_table(name, action, expected):
    verdict = govern(action)
    assert isinstance(verdict, Verdict)
    assert verdict.decision == expected, verdict.reason
    assert verdict.policy_ref  # every verdict must cite its policy section


def test_verdicts_always_cite_policy_and_reason():
    v = govern(ProposedAction("archive", UNKNOWN))
    assert v.reason and v.policy_ref


def test_archive_with_insufficient_content_is_hitl():
    v = govern(ProposedAction("archive", UNKNOWN, flags=frozenset({"insufficient_content"})))
    assert v.decision == Decision.HITL
