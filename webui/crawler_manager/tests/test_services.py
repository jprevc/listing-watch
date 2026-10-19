import contextlib
import threading

import pytest

from crawler_manager import services
from crawler_manager.models import CrawlRun, FoundItem, NotificationProfile, Query, QueryNotificationConfig
from listing_watch.config_field import ConfigField
from listing_watch.notificators import Notificator
from listing_watch.spiders import Spider

pytestmark = pytest.mark.django_db


class _FakeSpider:
    items: list[dict] = []

    def __init__(self, query_name, url, config=None):
        self.query_name = query_name
        self.url = url

    def run(self, max_pages=None, should_stop=None):
        return self.items


class _Pigeon(Notificator):
    """Records every message it sends, as (subject, message), and raises instead while `down` is set."""

    name = "pigeon"
    down = False
    sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        if self.down:
            raise ConnectionError("no wind")
        self.sent.append((subject, message))


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="test_query", spider_name="cars", url="https://example.com")


@pytest.fixture(name="sent")
def sent_fixture(query: Query, installed_plugins) -> list[tuple[str, str]]:
    """Installs `_FakeSpider` and `_Pigeon`, attaching a pigeon Profile to `query`; returns what it sends."""
    _Pigeon.sent, _Pigeon.down = [], False
    installed_plugins(spiders={"cars": _FakeSpider}, notificators={"pigeon": _Pigeon})
    profile = NotificationProfile.objects.create(name="carrier", notificator_name="pigeon", config={})
    QueryNotificationConfig.objects.create(query=query, profile=profile, message_body_format="{title}")
    return _Pigeon.sent


def test_run_query_persists_items_and_creates_successful_run(query: Query, sent) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]

    run = services.run_query(query, trigger=CrawlRun.Trigger.MANUAL)

    assert run.status == CrawlRun.Status.SUCCESS
    assert run.items_found_count == 1
    assert run.new_items_count == 1
    assert FoundItem.objects.filter(query=query).count() == 1
    assert sent == [("test_query news", "Query: test_query\n\nitem 1")]
    assert run.pending_deliveries_count == 0
    assert run.delivery_errors == ""


def test_run_query_dedups_on_second_run(query: Query, installed_plugins) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]
    installed_plugins(spiders={"cars": _FakeSpider})

    first_run = services.run_query(query)
    second_run = services.run_query(query)

    assert second_run.new_items_count == 0
    assert second_run.items_found_count == 1
    assert FoundItem.objects.filter(query=query).count() == 1

    # The item still belongs (by "run") to whichever run first created it, but "last_seen_run"
    # tracks the most recent run that re-matched it -- lets the "Found" count on any run link
    # back to the items that made it up, not just brand-new ones.
    item = FoundItem.objects.get(query=query)
    assert item.run_id == first_run.pk
    assert item.last_seen_run_id == second_run.pk


def test_run_query_marks_failed_on_exception(query: Query, installed_plugins) -> None:
    class _ExplodingSpider(_FakeSpider):
        def run(self, max_pages=None, should_stop=None):
            raise RuntimeError("site layout changed")

    installed_plugins(spiders={"cars": _ExplodingSpider})

    run = services.run_query(query)

    assert run.status == CrawlRun.Status.FAILED
    assert "site layout changed" in run.error_message


def test_run_query_marks_failed_when_spider_is_not_installed(query: Query, installed_plugins) -> None:
    installed_plugins(spiders={})

    run = services.run_query(query)

    assert run.status == CrawlRun.Status.FAILED
    assert run.error_message == "No installed Plugin provides a Spider named 'cars'."


def test_run_query_marks_cancelled_when_stop_requested_mid_run_and_delivers_what_it_found(
    query: Query, sent, installed_plugins
) -> None:
    # Simulates a "Stop" click landing while the spider is still crawling: the spider sees the
    # stop and returns whatever it had already collected.
    stop = threading.Event()

    class _CancellingSpider(_FakeSpider):
        items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]

        def run(self, max_pages=None, should_stop=None):
            stop.set()
            assert should_stop()
            return self.items

    installed_plugins(spiders={"cars": _CancellingSpider}, notificators={"pigeon": _Pigeon})

    run = services.run_query(query, stop_signal=lambda run: contextlib.nullcontext(stop.is_set))

    assert run.status == CrawlRun.Status.CANCELLED
    assert run.items_found_count == 1
    assert FoundItem.objects.filter(query=query).count() == 1
    assert sent == [("test_query news", "Query: test_query\n\nitem 1")]


def test_run_query_passes_its_spider_config_to_the_spider(installed_plugins) -> None:
    received_configs = []

    class _ConfiguredSpider(Spider):
        name = "cars"
        config_fields = (ConfigField(key="region", label="Region", required=True),)

        def run(self, max_pages=None, should_stop=None):
            received_configs.append(self.config)
            return []

    installed_plugins(spiders={"cars": _ConfiguredSpider})
    query = Query.objects.create(
        name="q1", spider_name="cars", url="https://example.com", spider_config={"region": "north"}
    )

    run = services.run_query(query)

    assert run.status == CrawlRun.Status.SUCCESS
    assert received_configs == [{"region": "north"}]


def test_run_query_skips_an_unavailable_profile_and_still_succeeds_and_sends_the_others(query: Query, sent) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1"}]
    unavailable = NotificationProfile.objects.create(name="old smoke", notificator_name="smoke", config={})
    QueryNotificationConfig.objects.create(query=query, profile=unavailable, message_body_format="{title}")

    run = services.run_query(query)

    assert sent == [("test_query news", "Query: test_query\n\nitem 1")]
    assert run.status == CrawlRun.Status.SUCCESS
    assert run.error_message == ""
    assert run.pending_deliveries_count == 1
    assert run.delivery_errors == (
        "old smoke (smoke): Skipped (Unavailable): No installed Plugin provides a Notificator named 'smoke'."
    )
    assert FoundItem.objects.filter(query=query).count() == 1


def test_run_query_records_a_send_failure_on_a_successful_run(query: Query, sent) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1"}]
    _Pigeon.down = True

    run = services.run_query(query)

    assert run.status == CrawlRun.Status.SUCCESS
    assert run.error_message == ""
    assert run.pending_deliveries_count == 1
    assert run.delivery_errors == "carrier (pigeon): no wind"


def test_run_query_sends_pending_deliveries_even_when_nothing_new_is_found(query: Query, sent) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1"}]
    _Pigeon.down = True
    services.run_query(query)
    _Pigeon.down = False

    run = services.run_query(query)

    assert run.new_items_count == 0
    assert sent == [("test_query news", "Query: test_query\n\nitem 1")]
    assert run.pending_deliveries_count == 0
    assert run.delivery_errors == ""


def test_run_query_does_not_deliver_when_the_crawl_fails(query: Query, sent, installed_plugins) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1"}]
    _Pigeon.down = True
    services.run_query(query)
    _Pigeon.down = False

    class _ExplodingSpider(_FakeSpider):
        def run(self, max_pages=None, should_stop=None):
            raise RuntimeError("site layout changed")

    installed_plugins(spiders={"cars": _ExplodingSpider}, notificators={"pigeon": _Pigeon})
    run = services.run_query(query)

    assert run.status == CrawlRun.Status.FAILED
    assert sent == []
