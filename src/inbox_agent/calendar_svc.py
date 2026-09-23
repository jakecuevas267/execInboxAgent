"""Calendar service: fixture-backed lookups and deterministic conflict math.

Interval logic lives here, in code, on purpose: date/boundary arithmetic is
exactly the kind of work an LLM gets subtly wrong, and a wrong answer here
either declines a meeting that was fine or books over protected time.

Conflict rule (policy §1): intervals conflict when they OVERLAP; touching a
boundary (end == block start, or start == block end) is NOT a conflict.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class ConflictResult:
    conflict: bool
    block_id: str | None
    block_label: str | None
    open_slots_hint: list


class CalendarService:
    def __init__(self, fixture_path: str | Path):
        self._data = json.loads(Path(fixture_path).read_text())

    def check_invite(self, invite_date: str, start: str, end: str) -> ConflictResult:
        """invite_date: YYYY-MM-DD; start/end: HH:MM (fixture timezone)."""
        d = date.fromisoformat(invite_date)
        s = time.fromisoformat(start)
        e = time.fromisoformat(end)
        if e <= s:
            raise ValueError(f"invite ends ({end}) at or before it starts ({start})")

        for block in self._data["protected_blocks"]:
            if not self._block_applies(block, d):
                continue
            b_start = time.fromisoformat(block["start"])
            b_end = time.fromisoformat(block["end"])
            # Strict overlap: touching boundaries is allowed.
            if s < b_end and e > b_start:
                return ConflictResult(True, block["id"], block["label"],
                                      self._data.get("open_slots_hint", []))
        return ConflictResult(False, None, None, self._data.get("open_slots_hint", []))

    @staticmethod
    def _block_applies(block: dict, d: date) -> bool:
        if "dates" in block:
            return d.isoformat() in block["dates"]
        if "days" in block:
            return WEEKDAY_NAMES[d.weekday()] in block["days"]
        return False

    def events_on(self, invite_date: str) -> list:
        return [e for e in self._data["events"] if e["date"] == invite_date]
