"""
Orchestration adapter: runs a single Query through the existing listing_watch spider/notificator
code, persisting results as CrawlRun/FoundItem rows instead of the old JSON-file cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from django.db import OperationalError, connection
from django.utils import timezone

from listing_watch import registry, spiders

from crawler_manager.delivery import DeliveryOutcome, deliver
from crawler_manager.failing import update_failing
from crawler_manager.models import CrawlRun, FoundItem, Query
from crawler_manager.run_outcome import decide_run_outcome

logger = logging.getLogger(__name__)

# How often `poll_cancel_requested`'s background thread re-checks CrawlRun.cancel_requested.
CANCEL_POLL_INTERVAL_SECONDS = 0.5


def _content_hash(item: spiders.SpiderItem) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _persist_and_diff(query: Query, crawled_items: list[spiders.SpiderItem], run: CrawlRun) -> list[FoundItem]:
    new_items: list[FoundItem] = []
    for item in crawled_items:
        item_hash = _content_hash(item)
        found_item, created = FoundItem.objects.get_or_create(
            spider_name=query.spider_name,
            query_name=query.name,
            content_hash=item_hash,
            defaults={
                "query": query,
                "user": query.user,
                "run": run,
                "last_seen_run": run,
                "payload": item,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "price": item.get("price", ""),
            },
        )
        if created:
            new_items.append(found_item)
        else:
            found_item.last_seen_run = run
            found_item.save(update_fields=["last_seen_run"])
    return new_items


# Supplies a run's stop signal: called with the new CrawlRun, it returns a context manager that
# yields the Spider's `should_stop` for as long as the crawl lasts.
StopSignal = Callable[[CrawlRun], AbstractContextManager[Callable[[], bool]]]


@contextmanager
def poll_cancel_requested(run: CrawlRun) -> Iterator[Callable[[], bool]]:
    """
    The production stop signal: true once the run's `cancel_requested` is set (by the "Stop" action).

    The `should_stop` it yields must never touch the Django ORM directly: a browser-driven Spider
    may call it from inside Playwright's `with sync_playwright()`, whose sync API drives its event
    loop via greenlets on the *calling* thread -- so `asyncio.get_running_loop()` succeeds there for
    the whole duration of that block, and any ORM access in that call stack raises Django's
    SynchronousOnlyOperation ("You cannot call this from an async context"). So the actual DB
    polling happens on a separate plain thread, and the spider only ever reads an in-memory flag
    that thread sets.
    """
    cancel_requested = threading.Event()
    stop_polling = threading.Event()

    def _poll() -> None:
        try:
            while not stop_polling.is_set():
                try:
                    if CrawlRun.objects.filter(pk=run.pk, cancel_requested=True).exists():
                        cancel_requested.set()
                        return
                except OperationalError:
                    # SQLite can transiently raise "database is locked" when this read overlaps
                    # a writer (e.g. the view flipping cancel_requested, or run_query's own
                    # writes) -- just retry on the next tick rather than losing the ability to
                    # ever detect a stop request for the rest of this run.
                    logger.warning("Cancel-request poll hit a transient DB error, retrying.", exc_info=True)
                stop_polling.wait(timeout=CANCEL_POLL_INTERVAL_SECONDS)
        finally:
            connection.close()

    poller = threading.Thread(target=_poll, name="cancel-request-poller", daemon=True)
    poller.start()
    try:
        yield cancel_requested.is_set
    finally:
        stop_polling.set()


def run_query(
    query: Query, trigger: str = CrawlRun.Trigger.MANUAL, *, stop_signal: StopSignal | None = None
) -> CrawlRun:
    """
    Runs a single query's spider, persists newly found items, and delivers them along with any
    still-pending ones.

    `stop_signal` defaults to `poll_cancel_requested`, the "Stop" action's DB flag.

    Never raises: failures are recorded on the returned CrawlRun instead. A failed crawl delivers
    nothing; a finished one is `success` (or `cancelled`) whatever happened to its Deliveries (see
    `decide_run_outcome`). Once the outcome is saved, the run counts toward whether the Query is
    Failing (see `update_failing`).
    """
    # The very first successful run for a query always crawls all pages, regardless of
    # `max_pages`, so the item history gets fully populated before later runs start only
    # skimming the first few pages for new listings.
    is_first_run = not query.runs.filter(status=CrawlRun.Status.SUCCESS).exists()
    max_pages = None if is_first_run else query.max_pages

    run = CrawlRun.objects.create(
        query=query,
        user=query.user,
        query_name=query.name,
        spider_name=query.spider_name,
        trigger=trigger,
        status=CrawlRun.Status.RUNNING,
        started_at=timezone.now(),
    )

    crawl_error: Exception | None = None
    delivery: DeliveryOutcome | None = None
    delivery_error: Exception | None = None
    with (stop_signal or poll_cancel_requested)(run) as should_stop:
        try:
            spider_cls = registry.installed().get_spider(query.spider_name)
            crawled_items = spider_cls(query.name, query.url, config=query.spider_config).run(
                max_pages=max_pages, should_stop=should_stop
            )

            new_items = _persist_and_diff(query, crawled_items, run)
            run.items_found_count = len(crawled_items)
            run.new_items_count = len(new_items)
        except Exception as exc:  # pylint: disable=broad-except
            crawl_error = exc
            logger.exception("Query run failed for %s", query)
        stop_requested = should_stop()

    # A stopped run still keeps (and delivers) whatever was found up to that point.
    if crawl_error is None:
        # Runs even with no new Items, to retry the Deliveries earlier runs left pending. Nothing
        # that goes wrong here fails the finished crawl: Items not delivered stay pending.
        try:
            delivery = deliver(query, new_items)
        except Exception as exc:  # pylint: disable=broad-except
            delivery_error = exc
            logger.exception("Delivery failed for %s", query)

    decide_run_outcome(
        crawl_error=crawl_error, stop_requested=stop_requested, delivery=delivery, delivery_error=delivery_error
    ).record_on(run)
    run.finished_at = timezone.now()
    run.save()

    # After the save, so this run is part of the history it counts. Nothing here changes the run.
    try:
        update_failing(query, run)
    except Exception:  # pylint: disable=broad-except
        logger.exception("Updating whether %s is Failing failed", query)

    return run
