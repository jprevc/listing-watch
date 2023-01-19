"""
Contains tests for Notificator classes.
"""
from __future__ import annotations

from itertools import product
import os

import pytest

from news_crawlers import notificators
from tests.mocks import HttpsSessionMock, SmtpMock


def get_test_messages_combinations() -> list[tuple[str, int, int, int]]:
    num_test_messages = [1, 5, 10, 100]
    test_message_characters = [600, 300, 200]
    num_test_users = [1, 2, 3, 4]

    # create different test combinations for parameterization
    test_combs = list(product(num_test_messages, test_message_characters, num_test_users))

    comb_names = [
        f"{num_messages}_messages_{num_chars}_chars_{num_users}_users"
        for (num_messages, num_chars, num_users) in test_combs
    ]

    return [(comb_name, *test_comb) for comb_name, test_comb in zip(comb_names, test_combs)]  # noqa


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


@pytest.mark.parametrize("_,num_test_items,text_length,num_users", get_test_messages_combinations())
def test_minimal_number_of_sent_messages_when_divided(
    pushover_notificator: notificators.PushoverNotificator,
    session_mock: HttpsSessionMock,
    _,
    num_test_items: int,
    text_length: int,
    num_users: int,
):
    """
    Test that 'send_items' method correctly divides items if length of message exceeds 1024 characters.
    """
    _send_test_items(pushover_notificator, num_test_items, text_length, num_users, send_separately=True)

    # minimal needed number of messages would occur if length of messages is perfectly divisible by 1024
    min_number_of_messages = (((text_length * num_test_items) // 1025) + 1) * num_users

    assert min_number_of_messages <= len(session_mock.simulated_messages)


@pytest.mark.parametrize("_,num_test_items,text_length,num_users", get_test_messages_combinations())
def test_length_of_message_must_be_less_than_1024(
    pushover_notificator: notificators.PushoverNotificator,
    session_mock: HttpsSessionMock,
    _,
    num_test_items: int,
    text_length: int,
    num_users: int,
):
    """
    Test that 'send_items' method never sends a message where length exceeds char limit of 1024.
    """
    _send_test_items(pushover_notificator, num_test_items, text_length, num_users, send_separately=True)

    # check that length of each message does not exceed 1024
    for message in session_mock.simulated_messages:
        assert len(message) <= 1024


@pytest.mark.parametrize("_,num_test_items,text_length,num_users", get_test_messages_combinations())
def test_length_of_divided_messages_is_equal_to_original(
    pushover_notificator: notificators.PushoverNotificator,
    session_mock: HttpsSessionMock,
    _,
    num_test_items: int,
    text_length: int,
    num_users: int,
):
    """
    Test that total length of divided items in 'send_items' method is equal to original message.
    """
    _send_test_items(pushover_notificator, num_test_items, text_length, num_users, send_separately=True)

    # check that sum of all messages lengths is equal to original text length
    messages_length_sum = sum(len(message) for message in session_mock.simulated_messages)
    original_txt_length = text_length * num_test_items * num_users
    assert original_txt_length == messages_length_sum


@pytest.mark.parametrize("_,num_test_items,text_length,num_users", get_test_messages_combinations())
def test_send_items_separate_correctly_separates_items(
    pushover_notificator: notificators.PushoverNotificator,
    session_mock: HttpsSessionMock,
    _,
    num_test_items: int,
    text_length: int,
    num_users: int,
):
    """
    Test that 'send_items' method correctly sends each item separately if that is specified.
    """
    _send_test_items(pushover_notificator, num_test_items, text_length, num_users, send_separately=True)

    assert num_test_items * num_users == len(session_mock.simulated_messages)


def _send_test_items(pushover, num_test_items, text_length, num_users, send_separately):
    items = [{"data": "a" * text_length}] * num_test_items
    pushover.configuration["recipients"] = ",".join(["user_key"] * num_users)

    pushover.send_items("Test subject", items, "{data}", send_separately=send_separately)


@pytest.mark.parametrize(
    "notificator_name,expected",
    [
        ("email", notificators.EmailNotificator),
        ("pushover", notificators.PushoverNotificator),
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


def test_handle_secrets_in_configuration():
    os.environ["TEST_1"] = "test_val_1"
    parsed_config = notificators.handle_secrets_in_configuration(
        {"test_key_1": "__env_TEST_1", "test_key_2": "test_val_2"}
    )
    assert parsed_config == {"test_key_1": "test_val_1", "test_key_2": "test_val_2"}
