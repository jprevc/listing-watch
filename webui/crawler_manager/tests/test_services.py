import time

import pytest

from crawler_manager import services
from crawler_manager.models import CrawlRun, FoundItem, NotificationProfile, Query, QueryNotificationConfig

pytestmark = pytest.mark.django_db


class _FakeSpider:
    items: list[dict] = []

    def __init__(self, queries):
        self.queries = queries

    def run(self, max_pages=None, should_stop=None):
        return self.items


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="test_query", spider_name="example", url="https://example.com")


def test_run_query_persists_items_and_creates_successful_run(query: Query, monkeypatch) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]
    monkeypatch.setattr(services.spiders, "get_spider_by_name", lambda name: _FakeSpider)

    sent = []
    monkeypatch.setattr(services.scrape, "send_notifications", lambda *args: sent.append(args))

    profile = NotificationProfile.objects.create(
        user=query.user, name="test profile", notificator_name="email", config={"recipients": "a@b.com"}
    )
    QueryNotificationConfig.objects.create(query=query, profile=profile, message_body_format="{title}")

    run = services.run_query(query, trigger=CrawlRun.Trigger.MANUAL)

    assert run.status == CrawlRun.Status.SUCCESS
    assert run.items_found_count == 1
    assert run.new_items_count == 1
    assert FoundItem.objects.filter(query=query).count() == 1
    assert len(sent) == 1


def test_run_query_dedups_on_second_run(query: Query, monkeypatch) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]
    monkeypatch.setattr(services.spiders, "get_spider_by_name", lambda name: _FakeSpider)
    monkeypatch.setattr(services.scrape, "send_notifications", lambda *args: None)

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


def test_run_query_marks_failed_on_exception(query: Query, monkeypatch) -> None:
    def _raise(name):
        raise KeyError("no such spider")

    monkeypatch.setattr(services.spiders, "get_spider_by_name", _raise)

    run = services.run_query(query)

    assert run.status == CrawlRun.Status.FAILED
    assert "no such spider" in run.error_message


@pytest.mark.django_db(transaction=True)
def test_run_query_marks_cancelled_when_stop_requested_mid_run(query: Query, monkeypatch) -> None:
    # Simulates a "Stop" click landing while the spider is still crawling: the fake spider flips
    # cancel_requested on the in-progress CrawlRun (mimicking the view) before returning whatever
    # it had already collected. run_query polls that flag on a separate thread (see services.py's
    # comment on why -- Playwright's sync API makes ORM access from the spider's own call stack
    # unsafe), so the fake spider has to wait it out like the real exampleSpider pagination loop
    # does, rather than asserting `should_stop()` flips true immediately.
    # `transaction=True` is required here (not the module-level plain `django_db`): the poller
    # thread reads through its own DB connection, which only sees committed rows -- a plain
    # `django_db` test wraps everything in one uncommitted outer transaction the poller can't see.
    class _CancellingSpider:
        items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]

        def __init__(self, queries):
            self.queries = queries

        def run(self, max_pages=None, should_stop=None):
            query.runs.update(cancel_requested=True)
            for _ in range(100):
                if should_stop():
                    return self.items
                time.sleep(0.05)
            pytest.fail("should_stop() never became true")
            return []  # pragma: no cover - unreachable, satisfies type checkers

    monkeypatch.setattr(services.spiders, "get_spider_by_name", lambda name: _CancellingSpider)
    monkeypatch.setattr(services.scrape, "send_notifications", lambda *args: None)

    run = services.run_query(query)

    assert run.status == CrawlRun.Status.CANCELLED
    assert run.items_found_count == 1
    assert FoundItem.objects.filter(query=query).count() == 1
