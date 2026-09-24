"""The production seam stays honest: fixtures work, stubs refuse loudly."""

import pytest

from inbox_agent.connectors import FixtureInbox, GmailInbox, MockSender


def test_fixture_inbox_reads_single_email():
    emails = FixtureInbox("demo/vip_email.json").fetch_unprocessed()
    assert len(emails) == 1 and emails[0]["from_email"] == "jim.calloway@apexretail.com"


def test_fixture_inbox_reads_case_list():
    emails = FixtureInbox("datasets/golden_inbox.json").fetch_unprocessed()
    assert len(emails) == 50


def test_mock_sender_records_instead_of_sending():
    s = MockSender()
    s.send_reply("jim@apexretail.com", "Re: Chicago", "on it - Dana")
    assert s.sent[0]["kind"] == "reply"


def test_gmail_stub_refuses_until_implemented():
    with pytest.raises(NotImplementedError):
        GmailInbox().fetch_unprocessed()
