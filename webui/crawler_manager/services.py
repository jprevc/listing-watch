"""
Orchestration adapter: runs a single Query through the existing listing_watch spider/notificator
code, persisting results as CrawlRun/FoundItem rows instead of the old JSON-file cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading

from django.db import OperationalError, connection
from django.utils import timezone

from listing_watch import registry, scrape, spiders

from crawler_manager.models import CrawlRun, FoundItem, Query

logger = logging.getLogger(__name__)

# How often the background thread below re-checks CrawlRun.cancel_requested.
CANCEL_POLL_INTERVAL_SECONDS = 0.5


def _content_hash(item: spiders.SpiderItem) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _persist_and_diff(query: Query, crawled_items: list[spiders.SpiderItem], run: CrawlRun) -> list[spiders.SpiderItem]:
    new_items: list[spiders.SpiderItem] = []
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
            new_items.append(item)
        else:
            found_item.last_seen_run = run
            found_item.save(update_fields=["last_seen_run"])
    return new_items


def run_query(query: Query, trigger: str = CrawlRun.Trigger.MANUAL) -> CrawlRun:
    """
    Runs a single query's spider, persists newly found items, and sends notifications for them.

    Never raises: failures are recorded on the returned CrawlRun instead.
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
    # `should_stop` (passed into the spider below) must never touch the Django ORM directly:
    # exampleSpider calls it from inside `with sync_playwright()`, whose sync API drives its event
    # loop via greenlets on the *calling* thread -- so `asyncio.get_running_loop()` succeeds there
    # for the whole duration of that block, and any ORM access in that call stack raises
    # Django's SynchronousOnlyOperation ("You cannot call this from an async context"). So the
    # actual DB polling happens on a separate plain thread, and the spider only ever reads an
    # in-memory flag that thread sets.
    cancel_requested = threading.Event()
    stop_polling = threading.Event()

    def _poll_cancel_requested() -> None:
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

    poller = threading.Thread(target=_poll_cancel_requested, daemon=True)
    poller.start()

    try:
        spider_cls = registry.installed().get_spider(query.spider_name)
        crawled_items = spider_cls(query.name, query.url, config=query.spider_config).run(
            max_pages=max_pages, should_stop=cancel_requested.is_set
        )

        new_items = _persist_and_diff(query, crawled_items, run)
        run.items_found_count = len(crawled_items)
        run.new_items_count = len(new_items)

        if new_items:
            # A list of (label, type, config) triples rather than a dict keyed by type: a query can
            # attach more than one profile of the same notificator type (e.g. two ntfy topics), and
            # each attachment must still fire independently and be named on its own if it fails.
            notification_configs = [
                (
                    str(nc.profile),
                    nc.profile.notificator_name,
                    {**nc.profile.config, "message_body_format": nc.message_body_format},
                )
                for nc in query.notification_configs.select_related("profile")
            ]
            scrape.send_notifications(notification_configs, query.name, new_items)

        # A stopped run still keeps whatever was found up to that point -- only the terminal
        # status differs from a normal completion.
        run.status = CrawlRun.Status.CANCELLED if cancel_requested.is_set() else CrawlRun.Status.SUCCESS
    except Exception as exc:  # pylint: disable=broad-except
        run.status = CrawlRun.Status.FAILED
        run.error_message = str(exc)
        logger.exception("Query run failed for %s", query)
    finally:
        stop_polling.set()
        run.finished_at = timezone.now()
        run.save()

    return run
