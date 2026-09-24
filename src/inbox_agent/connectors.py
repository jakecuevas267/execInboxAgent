"""The production seam: where a real mailbox plugs in.

The pipeline consumes plain email dicts ({from_name, from_email, subject,
body, invite?}) and never knows where they came from. These connectors are
the only code that changes between the demo and a client deployment - the
agent, governance engine, evals, and traces are untouched.

Demo:        FixtureInbox + MockSender (what the eval runner and CLI use
             conceptually today).
Production:  GmailInbox + GmailSender (stubs below document exactly what
             the wiring entails - they raise until implemented).
"""

import json
from pathlib import Path
from typing import Protocol


class InboxSource(Protocol):
    """Anything that can yield inbound emails in the pipeline's shape."""

    def fetch_unprocessed(self) -> list[dict]: ...


class ActionSender(Protocol):
    """Anything that can carry out an APPROVED outbound action.

    Only the executor calls this, only after a governance AUTO verdict or
    an explicit human approval - the trust model does not change with the
    transport."""

    def send_reply(self, to: str, subject: str, body: str) -> None: ...
    def decline_event(self, event_ref: str, note: str) -> None: ...


class FixtureInbox:
    """Demo source: emails from a JSON file (single email or a case list)."""

    def __init__(self, path: str | Path):
        self._path = Path(path)

    def fetch_unprocessed(self) -> list[dict]:
        data = json.loads(self._path.read_text())
        if isinstance(data, dict) and "cases" in data:
            return [c["email"] for c in data["cases"]]
        return [data["email"] if "email" in data else data]


class MockSender:
    """Demo sink: 'sending' is appending to a log. Nothing leaves."""

    def __init__(self):
        self.sent: list[dict] = []

    def send_reply(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"kind": "reply", "to": to, "subject": subject, "body": body})

    def decline_event(self, event_ref: str, note: str) -> None:
        self.sent.append({"kind": "decline", "event": event_ref, "note": note})


class GmailInbox:
    """Production stub. Implementing this - and nothing else - connects a
    client's real mailbox:

    1. Auth: OAuth2 with gmail.readonly (fetch) via the client's Workspace
       admin; tokens in a secret manager, never in code or env files.
    2. Ingest: users.messages.list on a label/query for polling, or
       users.watch + Pub/Sub push for near-real-time.
    3. Normalize: Gmail payload -> the pipeline's email dict. Sender
       identity STAYS address-based (headers parsed here, verified against
       the directory by IdentityService, exactly as with fixtures).
    4. Idempotency: track processed message ids so restarts don't re-triage.

    The gateway scan, agent, governance engine, and evals are unchanged -
    real mail is just a different fetch_unprocessed().
    """

    def __init__(self, credentials=None):
        self._credentials = credentials

    def fetch_unprocessed(self) -> list[dict]:
        raise NotImplementedError("production wiring - see class docstring")


class GmailSender:
    """Production stub for the outbound side: gmail.send +
    calendar.events.patch (decline), called ONLY by the executor after
    governance/HITL approval. Scopes are the write-side blast radius, so
    they live on a separate service identity from the read-side."""

    def __init__(self, credentials=None):
        self._credentials = credentials

    def send_reply(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError("production wiring - see class docstring")

    def decline_event(self, event_ref: str, note: str) -> None:
        raise NotImplementedError("production wiring - see class docstring")
