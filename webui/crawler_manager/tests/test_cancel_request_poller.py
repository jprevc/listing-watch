import threading
import time
from collections.abc import Callable

import pytest
from django.db import OperationalError

from crawler_manager import services
from crawler_manager.models import CrawlRun, Query

# The poller thread reads through its own DB connection, which only sees committed rows -- a plain
# `django_db` test wraps everything in one uncommitted outer transaction the poller can't see.
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.cancel_request_poller]


@pytest.fixture(name="run")
def run_fixture() -> CrawlRun:
    query = Query.objects.create(name="test_query", spider_name="cars", url="https://example.com")
    return CrawlRun.objects.create(
        query=query, query_name=query.name, spider_name=query.spider_name, status=CrawlRun.Status.RUNNING
    )


def _becomes_true(should_stop: Callable[[], bool], timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if should_stop():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture(autouse=True)
def _fast_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "CANCEL_POLL_INTERVAL_SECONDS", 0.01)


def test_should_stop_turns_true_once_a_stop_is_requested_on_the_run(run: CrawlRun) -> None:
    with services.poll_cancel_requested(run) as should_stop:
        assert not should_stop()

        CrawlRun.objects.filter(pk=run.pk).update(cancel_requested=True)

        assert _becomes_true(should_stop)


def test_the_poller_retries_after_a_transient_db_error(run: CrawlRun, monkeypatch: pytest.MonkeyPatch) -> None:
    CrawlRun.objects.filter(pk=run.pk).update(cancel_requested=True)
    real_filter = CrawlRun.objects.filter
    failures_left = [2]

    def _locked_at_first(*args, **kwargs):
        if failures_left[0]:
            failures_left[0] -= 1
            raise OperationalError("database is locked")
        return real_filter(*args, **kwargs)

    monkeypatch.setattr(CrawlRun.objects, "filter", _locked_at_first)

    with services.poll_cancel_requested(run) as should_stop:
        assert _becomes_true(should_stop)

    assert failures_left == [0]


def test_the_poller_stops_when_the_run_ends(run: CrawlRun) -> None:
    with services.poll_cancel_requested(run):
        assert any(thread.name == "cancel-request-poller" for thread in threading.enumerate())

    for thread in threading.enumerate():
        if thread.name == "cancel-request-poller":
            thread.join(timeout=5.0)
            assert not thread.is_alive()


def test_run_query_stops_on_a_stop_requested_in_the_db_by_default(run: CrawlRun, installed_plugins) -> None:
    query = run.query

    class _StoppableSpider:
        def __init__(self, query_name, url, config=None):
            pass

        def run(self, max_pages=None, should_stop=None):
            query.runs.filter(status=CrawlRun.Status.RUNNING).exclude(pk=run.pk).update(cancel_requested=True)
            assert _becomes_true(should_stop)
            return []

    installed_plugins(spiders={"cars": _StoppableSpider})

    assert services.run_query(query).status == CrawlRun.Status.CANCELLED
