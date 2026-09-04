"""
Contains tests for Notificator classes.
"""
from __future__ import annotations

import pytest

from listing_watch import notificators
from tests.mocks import HttpsSessionMock, NtfySessionMock, SmtpMock


@pytest.fixture(name="session_mock")
def session_mock_fixture() -> HttpsSessionMock:
    return HttpsSessionMock()


@pytest.fixture(name="pushover_notificator")
def pushover_notificator_fixture(session_mock: HttpsSessionMock, monkeypatch) -> notificators.PushoverNotificator:
    config = {"app_token": "app_token", "recipients": "user_key_1"}

    pushover = notificators.PushoverNotificator(config)

    monkeypatch.setattr(pushover, "_open_session", lambda: session_mock)

    return pushover


def test_send_text(
    pushover_notificator: notificators.PushoverNotificator,
    session_mock: HttpsSessionMock,
) -> None:
    """
    Test that 'send_text' method correctly creates message text for a pushover notification.
    """
    pushover_notificator.send_text("test_subject", "test_message")
    assert session_mock.simulated_messages[0] == "test_message"


@pytest.mark.parametrize(
    "notificator_name,expected",
    [
        ("email", notificators.EmailNotificator),
        ("pushover", notificators.PushoverNotificator),
        ("ntfy", notificators.NtfyNotificator),
    ],
)
def test_get_notificator_by_name(notificator_name: str, expected: notificators.Notificator) -> None:
    assert notificators.get_notificator_by_name(notificator_name) == expected


@pytest.fixture(name="smtp_mock")
def smtp_mock_fixture() -> SmtpMock:
    return SmtpMock()


@pytest.fixture(name="email_notificator")
def email_notificator_fixture(smtp_mock: SmtpMock, monkeypatch) -> notificators.EmailNotificator:
    configuration = {
        "recipients": "user_key_1",
        "email_user": "test_email_user",
        "email_password": "test_email_pass",
    }

    email = notificators.EmailNotificator(configuration)

    monkeypatch.setattr(email, "_get_smtp_session", lambda: smtp_mock)

    return email


def test_send_email_text(email_notificator: notificators.EmailNotificator, smtp_mock: SmtpMock):
    """
    Test that 'send_text' method correctly creates message text for email.
    """
    email_notificator.send_text("test_subject", "test_message")
    assert smtp_mock.simulated_messages[0] == b"Subject: test_subject\n\ntest_message"


def test_get_notificator_by_name_raises_key_error_if_notificator_not_found():
    with pytest.raises(KeyError):
        assert notificators.get_notificator_by_name("notexistingnotificator")


@pytest.fixture(name="ntfy_session_mock")
def ntfy_session_mock_fixture() -> NtfySessionMock:
    return NtfySessionMock()


def _make_ntfy_notificator(session_mock: NtfySessionMock, monkeypatch, **config_overrides):
    config = {"topic": "test_topic", **config_overrides}
    ntfy = notificators.NtfyNotificator(config)
    monkeypatch.setattr(ntfy, "_open_session", lambda: session_mock)
    return ntfy


def test_ntfy_send_text(ntfy_session_mock: NtfySessionMock, monkeypatch) -> None:
    ntfy = _make_ntfy_notificator(ntfy_session_mock, monkeypatch)
    ntfy.send_text("test_subject", "test_message")

    assert ntfy_session_mock.simulated_messages[0] == "test_message"
    assert ntfy_session_mock.simulated_headers[0]["Title"] == "test_subject"


def test_ntfy_default_server_used_in_url(ntfy_session_mock: NtfySessionMock, monkeypatch) -> None:
    ntfy = _make_ntfy_notificator(ntfy_session_mock, monkeypatch)
    ntfy.send_text("subject", "message")

    assert ntfy_session_mock.simulated_urls[0] == "https://ntfy.sh/test_topic"


def test_ntfy_custom_server_used_in_url(ntfy_session_mock: NtfySessionMock, monkeypatch) -> None:
    ntfy = _make_ntfy_notificator(ntfy_session_mock, monkeypatch, server="https://ntfy.example.com/")
    ntfy.send_text("subject", "message")

    assert ntfy_session_mock.simulated_urls[0] == "https://ntfy.example.com/test_topic"


def test_ntfy_priority_and_tags_set_headers(ntfy_session_mock: NtfySessionMock, monkeypatch) -> None:
    ntfy = _make_ntfy_notificator(ntfy_session_mock, monkeypatch, priority="high", tags="warning,skull")
    ntfy.send_text("subject", "message")

    assert ntfy_session_mock.simulated_headers[0]["Priority"] == "high"
    assert ntfy_session_mock.simulated_headers[0]["Tags"] == "warning,skull"


def test_ntfy_token_sets_authorization_header(ntfy_session_mock: NtfySessionMock, monkeypatch) -> None:
    ntfy = _make_ntfy_notificator(ntfy_session_mock, monkeypatch, token="secret_token")
    ntfy.send_text("subject", "message")

    assert ntfy_session_mock.simulated_headers[0]["Authorization"] == "Bearer secret_token"
    assert ntfy_session_mock.simulated_auth[0] is None


def test_ntfy_username_password_sets_basic_auth(ntfy_session_mock: NtfySessionMock, monkeypatch) -> None:
    ntfy = _make_ntfy_notificator(ntfy_session_mock, monkeypatch, username="user", password="pass")
    ntfy.send_text("subject", "message")

    assert ntfy_session_mock.simulated_auth[0] == ("user", "pass")
    assert "Authorization" not in ntfy_session_mock.simulated_headers[0]


def test_send_items_shows_query_header_once_per_group(
    email_notificator: notificators.EmailNotificator, smtp_mock: SmtpMock
) -> None:
    """
    'send_items' (combined, non-separate mode) should print "Query: ..." once at the start of
    each run of same-query items, not once per item, and separate items with a blank line.
    """
    items = [
        {"query": "q1", "title": "a"},
        {"query": "q1", "title": "b"},
        {"query": "q2", "title": "c"},
    ]
    email_notificator.send_items("subject", items, "{title}")

    assert smtp_mock.simulated_messages[0] == (
        b"Subject: subject\n\nQuery: q1\n\na\n\nb\n\nQuery: q2\n\nc"
    )


def test_pushover_send_items_repeats_header_when_split_mid_query(
    pushover_notificator: notificators.PushoverNotificator, session_mock: HttpsSessionMock
) -> None:
    """
    When Pushover's 1024-char limit splits two same-query items across separate messages, the
    second message must still carry its own "Query: ..." header even though the query didn't
    change -- it's a standalone push notification with no visible link to the first message.
    """
    items = [
        {"query": "q1", "data": "a" * 600},
        {"query": "q1", "data": "b" * 600},
    ]
    pushover_notificator.send_items("subject", items, "{data}")

    assert len(session_mock.simulated_messages) == 2
    assert session_mock.simulated_messages[0] == f"Query: q1\n\n{'a' * 600}"
    assert session_mock.simulated_messages[1] == f"Query: q1\n\n{'b' * 600}"
