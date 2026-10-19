from collections.abc import Callable
from datetime import timedelta

import pytest
from django.utils import timezone

from crawler_manager.delivery import CLAIM_TIMEOUT, DeliveryOutcome, deliver
from crawler_manager.models import Delivery, FoundItem, NotificationProfile, Query, QueryNotificationConfig
from listing_watch.notificators import Notificator

pytestmark = pytest.mark.django_db


class _Pigeon(Notificator):
    """Records every message it sends, as (subject, message)."""

    name = "pigeon"
    sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        self.sent.append((subject, message))


@pytest.fixture(name="sent")
def sent_fixture(installed_plugins) -> list[tuple[str, str]]:
    _Pigeon.sent = []
    installed_plugins(notificators={"pigeon": _Pigeon})
    return _Pigeon.sent


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="cars", spider_name="cars", url="https://example.com")


def _attach(query: Query, name: str, notificator_name: str = "pigeon", message_body_format: str = "{title}"):
    profile = NotificationProfile.objects.create(name=name, notificator_name=notificator_name, config={})
    return QueryNotificationConfig.objects.create(query=query, profile=profile, message_body_format=message_body_format)


def _item(query: Query, title: str, /, **payload: str) -> FoundItem:
    return FoundItem.objects.create(
        query=query,
        query_name=query.name,
        spider_name=query.spider_name,
        title=title,
        payload={"title": title, "url": f"https://example.com/{title}", **payload},
        content_hash=title,
    )


def test_sends_new_items_to_an_attached_profile(query: Query, sent) -> None:
    _attach(query, "carrier")

    outcome = deliver(query, [_item(query, "a"), _item(query, "b")])

    assert sent == [("cars news", "Query: cars\n\na\n\nb")]
    assert outcome == DeliveryOutcome(pending_count=0, errors={})


def test_names_items_by_the_query_even_if_the_spider_set_its_own(query: Query, sent) -> None:
    _attach(query, "carrier", message_body_format="{title} ({query})")

    deliver(query, [_item(query, "a", query="something else")])

    assert sent == [("cars news", "Query: cars\n\na (cars)")]


class _Smoke(Notificator):
    """Sends like `_Pigeon`, but raises instead while `down` is set."""

    name = "smoke"
    down = False
    sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        if self.down:
            raise ConnectionError("no wind")
        self.sent.append((subject, message))


def test_a_profile_that_failed_receives_its_items_once_it_recovers_and_the_others_get_nothing_again(
    query: Query, installed_plugins
) -> None:
    _Pigeon.sent, _Smoke.sent, _Smoke.down = [], [], True
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    _attach(query, "carrier")
    _attach(query, "signal", notificator_name="smoke")

    first = deliver(query, [_item(query, "a")])

    assert _Pigeon.sent == [("cars news", "Query: cars\n\na")]
    assert _Smoke.sent == []
    assert first == DeliveryOutcome(pending_count=1, errors={"signal (smoke)": "no wind"})

    _Pigeon.sent, _Smoke.down = [], False
    second = deliver(query, [_item(query, "b")])

    assert _Pigeon.sent == [("cars news", "Query: cars\n\nb")]
    assert _Smoke.sent == [("cars news", "Query: cars\n\na\n\nb")]
    assert second == DeliveryOutcome(pending_count=0, errors={})

    _Pigeon.sent, _Smoke.sent = [], []
    third = deliver(query, [])

    assert _Pigeon.sent == _Smoke.sent == []
    assert third == DeliveryOutcome(pending_count=0, errors={})


def test_skips_an_unavailable_profile_and_keeps_its_deliveries_pending(query: Query, sent, installed_plugins) -> None:
    _attach(query, "old smoke", notificator_name="smoke")
    _attach(query, "carrier")

    first = deliver(query, [_item(query, "a")])

    assert sent == [("cars news", "Query: cars\n\na")]
    assert first == DeliveryOutcome(
        pending_count=1,
        errors={
            "old smoke (smoke)": "Skipped (Unavailable): No installed Plugin provides a Notificator named 'smoke'."
        },
    )

    sent.clear()
    _Smoke.sent, _Smoke.down = [], False
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    second = deliver(query, [])

    assert sent == []
    assert _Smoke.sent == [("cars news", "Query: cars\n\na")]
    assert second == DeliveryOutcome(pending_count=0, errors={})


def test_expires_a_pending_delivery_whose_item_was_first_seen_over_7_days_ago(query: Query, installed_plugins) -> None:
    _Pigeon.sent, _Smoke.sent, _Smoke.down = [], [], True
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    _attach(query, "signal", notificator_name="smoke")
    deliver(query, [_item(query, "stale"), _item(query, "recent")])
    FoundItem.objects.filter(title="stale").update(first_seen_at=timezone.now() - timedelta(days=7, minutes=1))
    FoundItem.objects.filter(title="recent").update(first_seen_at=timezone.now() - timedelta(days=6, hours=23))
    _Smoke.down = False

    outcome = deliver(query, [])

    assert _Smoke.sent == [("cars news", "Query: cars\n\nrecent")]
    assert outcome == DeliveryOutcome(pending_count=0, errors={})


def test_moving_an_attachment_to_another_profile_drops_the_old_ones_pending_deliveries_and_gives_no_backlog(
    query: Query, installed_plugins
) -> None:
    _Pigeon.sent, _Smoke.sent, _Smoke.down = [], [], True
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    attachment = _attach(query, "signal", notificator_name="smoke")
    deliver(query, [_item(query, "a")])
    _Smoke.down = False

    attachment.profile = NotificationProfile.objects.create(name="carrier", notificator_name="pigeon", config={})
    attachment.save()
    moved = deliver(query, [])

    assert _Pigeon.sent == []
    assert moved == DeliveryOutcome(pending_count=0, errors={})


def test_moving_an_attachment_away_and_back_before_the_next_run_still_drops_the_pending_deliveries(
    query: Query, installed_plugins
) -> None:
    _Smoke.sent, _Smoke.down = [], True
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    attachment = _attach(query, "signal", notificator_name="smoke")
    old_profile = attachment.profile
    deliver(query, [_item(query, "a")])
    _Smoke.down = False

    attachment.profile = NotificationProfile.objects.create(name="carrier", notificator_name="pigeon", config={})
    attachment.save()
    attachment.profile = old_profile
    attachment.save()
    outcome = deliver(query, [])

    assert _Smoke.sent == []
    assert outcome == DeliveryOutcome(pending_count=0, errors={})


def test_deleting_a_query_drops_its_pending_deliveries_but_keeps_the_delivered_ones(
    query: Query, installed_plugins
) -> None:
    _Smoke.down = True
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    _attach(query, "carrier")
    _attach(query, "signal", notificator_name="smoke")
    deliver(query, [_item(query, "a")])

    query.delete()

    # Once the Query is gone no run can send them, so the Deliveries themselves are what's left to check.
    assert [(d.profile.name, d.status) for d in Delivery.objects.all()] == [("carrier", Delivery.Status.DELIVERED)]


def test_reports_an_unavailable_profile_as_skipped_even_with_nothing_pending(query: Query, sent) -> None:
    _attach(query, "old smoke", notificator_name="smoke")

    outcome = deliver(query, [])

    assert outcome == DeliveryOutcome(
        pending_count=0,
        errors={
            "old smoke (smoke)": "Skipped (Unavailable): No installed Plugin provides a Notificator named 'smoke'."
        },
    )


class _Echo(Notificator):
    """Sends like `_Pigeon`, but first runs `during_send` once, standing in for an overlapping run of the Query."""

    name = "echo"
    during_send: Callable[[], None] | None = None
    sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        during_send, type(self).during_send = type(self).during_send, None
        if during_send is not None:
            during_send()
        self.sent.append((subject, message))


@pytest.fixture(name="echo")
def echo_fixture(query: Query, installed_plugins) -> type[_Echo]:
    _Echo.sent, _Echo.during_send = [], None
    installed_plugins(notificators={"echo": _Echo})
    _attach(query, "carrier", notificator_name="echo")
    return _Echo


def test_an_overlapping_run_does_not_send_what_another_run_is_still_sending(query: Query, echo: type[_Echo]) -> None:
    overlapping: list[DeliveryOutcome] = []
    echo.during_send = lambda: overlapping.append(deliver(query, [_item(query, "b")]))

    outcome = deliver(query, [_item(query, "a")])

    assert echo.sent == [("cars news", "Query: cars\n\nb"), ("cars news", "Query: cars\n\na")]
    assert overlapping == [DeliveryOutcome(pending_count=1, errors={})]
    assert outcome == DeliveryOutcome(pending_count=0, errors={})


def test_a_run_that_died_mid_send_leaves_its_deliveries_to_a_run_15_minutes_later(
    query: Query, echo: type[_Echo], monkeypatch
) -> None:

    def _die() -> None:
        raise SystemExit("worker killed")

    echo.during_send = _die
    with pytest.raises(SystemExit):
        deliver(query, [_item(query, "a")])

    soon = deliver(query, [])

    assert echo.sent == []
    assert soon == DeliveryOutcome(pending_count=1, errors={})

    later = timezone.now() + CLAIM_TIMEOUT + timedelta(seconds=1)
    monkeypatch.setattr(timezone, "now", lambda: later)
    outcome = deliver(query, [])

    assert echo.sent == [("cars news", "Query: cars\n\na")]
    assert outcome == DeliveryOutcome(pending_count=0, errors={})
