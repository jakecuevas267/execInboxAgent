"""Boundary-heavy tests for calendar conflict math (policy §1)."""

import pytest

from inbox_agent.calendar_svc import CalendarService

FIXTURE = "fixtures/calendar.json"
# 2026-10-06 is a Tuesday; deep work 08:00-10:00, family 17:30-23:59.
# 2026-10-07 is the full-day board-prep block. 2026-10-10 is a Saturday.


@pytest.fixture(scope="module")
def cal():
    return CalendarService(FIXTURE)


@pytest.mark.parametrize("date,start,end,expect_conflict,expect_block", [
    # squarely inside deep work
    ("2026-10-06", "08:30", "09:15", True, "deep-work"),
    # partial overlaps on both edges
    ("2026-10-06", "07:30", "08:15", True, "deep-work"),
    ("2026-10-06", "09:45", "10:15", True, "deep-work"),
    # touching boundaries: NOT conflicts
    ("2026-10-06", "07:30", "08:00", False, None),
    ("2026-10-06", "10:00", "10:45", False, None),
    # envelope: invite fully contains the block
    ("2026-10-06", "07:00", "11:00", True, "deep-work"),
    # family block, weekday evening
    ("2026-10-06", "18:00", "19:00", True, "family"),
    ("2026-10-06", "17:00", "17:30", False, None),
    # family block does not apply on Saturday
    ("2026-10-10", "18:00", "18:45", False, None),
    # full-day board-prep date block
    ("2026-10-07", "11:00", "11:30", True, "board-prep"),
    # same time next day is fine
    ("2026-10-08", "11:00", "11:30", False, None),
])
def test_conflicts(cal, date, start, end, expect_conflict, expect_block):
    result = cal.check_invite(date, start, end)
    assert result.conflict is expect_conflict
    assert result.block_id == expect_block


def test_degenerate_invite_rejected(cal):
    with pytest.raises(ValueError):
        cal.check_invite("2026-10-06", "10:00", "10:00")
    with pytest.raises(ValueError):
        cal.check_invite("2026-10-06", "11:00", "10:00")


def test_conflict_result_carries_open_slots(cal):
    result = cal.check_invite("2026-10-06", "08:30", "09:00")
    assert result.conflict and result.open_slots_hint
