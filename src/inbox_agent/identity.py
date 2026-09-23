"""Sender identity resolution: deterministic, address-based.

Identity is the EMAIL ADDRESS, never the display name (fixtures note).
A display name that matches a known contact while the address does not is
the classic spoof pattern, so we surface it as a flag for the governance
engine rather than trusting the model to notice.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedSender:
    email: str
    known: bool
    internal: bool
    exec_team: bool
    vip: bool
    board: bool
    display_name_spoof: bool  # display name matches a contact, address does not


class IdentityService:
    def __init__(self, fixture_path: str | Path):
        contacts = json.loads(Path(fixture_path).read_text())["contacts"]
        self._by_email = {c["email"].lower(): c for c in contacts}
        self._names = {c["name"].lower(): c["email"].lower() for c in contacts}
        self._internal_domain = "meridianlog.com"

    def resolve(self, from_email: str, from_name: str = "") -> ResolvedSender:
        email = from_email.lower().strip()
        contact = self._by_email.get(email)
        known = contact is not None

        name_key = from_name.lower().strip()
        spoof = (
            name_key in self._names
            and self._names[name_key] != email
        )

        return ResolvedSender(
            email=email,
            known=known,
            internal=email.endswith("@" + self._internal_domain),
            exec_team=bool(contact and contact.get("exec_team")),
            vip=bool(contact and contact.get("vip")),
            board=bool(contact and contact.get("board")),
            display_name_spoof=spoof,
        )
