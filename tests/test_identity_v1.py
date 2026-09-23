"""Tests for the v1 identity additions (delegate resolution, sender profile)."""

import pytest

from inbox_agent.identity import IdentityService


@pytest.fixture(scope="module")
def ids():
    return IdentityService("fixtures/contacts.json")


def test_resolve_delegate_by_name(ids):
    assert ids.resolve_delegate("Marcus Rivera") == "marcus.rivera@meridianlog.com"
    assert ids.resolve_delegate("marcus rivera (COO)") == "marcus.rivera@meridianlog.com"


def test_resolve_delegate_by_email_passthrough(ids):
    assert ids.resolve_delegate("priya.shah@meridianlog.com") == "priya.shah@meridianlog.com"


def test_hallucinated_address_resolves_to_none_not_invention(ids):
    # The v0 failure: model invented marcus@meridianlogistics.com.
    assert ids.resolve_delegate("someone@nowhere.example") is None
    assert ids.resolve_delegate("") is None
    assert ids.resolve_delegate(None) is None


def test_describe_verified_contact(ids):
    d = ids.describe("jim.calloway@apexretail.com", "Jim Calloway")
    assert "Verified contact" in d and "VIP" in d


def test_describe_spoof(ids):
    d = ids.describe("jim.calloway@apex-retaii.com", "Jim Calloway")
    assert "spoof" in d.lower()


def test_describe_unknown(ids):
    d = ids.describe("stranger@example.com", "Stranger")
    assert "Unknown external" in d
