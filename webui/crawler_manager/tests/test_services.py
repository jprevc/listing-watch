import pytest

from crawler_manager import services
from crawler_manager.models import CrawlRun, FoundItem, Query, QueryNotificationConfig

pytestmark = pytest.mark.django_db


class _FakeSpider:
    items: list[dict] = []

    def __init__(self, queries):
        self.queries = queries

    def run(self, max_pages=None):
        return self.items


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="test_query", spider_name="example", url="https://example.com")


def test_run_query_persists_items_and_creates_successful_run(query: Query, monkeypatch) -> None:
    _FakeSpider.items = [{"title": "item 1", "url": "https://example.com/1", "price": "10"}]
    monkeypatch.setattr(services.spiders, "get_spider_by_name", lambda name: _FakeSpider)

    sent = []
    monkeypatch.setattr(services.scrape, "send_notifications", lambda *args: sent.append(args))

    QueryNotificationConfig.objects.create(query=query, notificator_name="email", config={"recipients": "a@b.com"})

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
