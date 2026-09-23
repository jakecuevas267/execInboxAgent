"""Tests for address-based sender resolution and spoof detection."""

import pytest

from inbox_agent.identity import IdentityService

FIXTURE = "fixtures/contacts.json"


@pytest.fixture(scope="module")
def ids():
    return IdentityService(FIXTURE)


def test_known_vip(ids):
    r = ids.resolve("jim.calloway@apexretail.com", "Jim Calloway")
    assert r.known and r.vip and not r.board and not r.display_name_spoof


def test_known_board_member(ids):
    r = ids.resolve("rchen@halcyonpartners.com", "Robert Chen")
    assert r.known and r.board and not r.display_name_spoof


def test_internal_exec(ids):
    r = ids.resolve("priya.shah@meridianlog.com", "Priya Shah")
    assert r.internal and r.exec_team


def test_internal_non_exec(ids):
    r = ids.resolve("sarah.kim@meridianlog.com", "Sarah Kim")
    assert r.internal and not r.exec_team


def test_unknown_sender(ids):
    r = ids.resolve("stranger@example.com", "Some Stranger")
    assert not r.known and not r.internal and not r.display_name_spoof


def test_typosquat_domain_with_vip_display_name_is_spoof(ids):
    r = ids.resolve("jim.calloway@apex-retaii.com", "Jim Calloway")
    assert not r.known
    assert r.display_name_spoof


def test_spoofed_internal_display_name(ids):
    r = ids.resolve("priya.shah@meridian-log.co", "Priya Shah")
    assert not r.known and not r.internal
    assert r.display_name_spoof


def test_case_insensitive_resolution(ids):
    r = ids.resolve("Jim.Calloway@ApexRetail.com", "jim calloway")
    assert r.known and r.vip and not r.display_name_spoof


def test_unknown_name_unknown_address_is_not_spoof(ids):
    r = ids.resolve("k.reyes.consulting@gmail.com", "Unknown")
    assert not r.display_name_spoof
