"""
Orchestration adapter: runs a single Query through the existing news_crawlers spider/notificator
code, persisting results as CrawlRun/FoundItem rows instead of the old JSON-file cache.
"""

from __future__ import annotations

import hashlib
import json
import logging

from django.utils import timezone

from news_crawlers import scrape, spiders

from crawler_manager.models import CrawlRun, FoundItem, Query

logger = logging.getLogger(__name__)


def _content_hash(item: spiders.SpiderItem) -> str:
    return hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _persist_and_diff(query: Query, crawled_items: list[spiders.SpiderItem], run: CrawlRun) -> list[spiders.SpiderItem]:
    new_items: list[spiders.SpiderItem] = []
    for item in crawled_items:
        item_hash = _content_hash(item)
        _, created = FoundItem.objects.get_or_create(
            spider_name=query.spider_name,
            query_name=query.name,
            content_hash=item_hash,
            defaults={
                "query": query,
                "run": run,
                "payload": item,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "price": item.get("price", ""),
            },
        )
        if created:
            new_items.append(item)
    return new_items


def run_query(query: Query, trigger: str = CrawlRun.Trigger.MANUAL) -> CrawlRun:
    """
    Runs a single query's spider, persists newly found items, and sends notifications for them.

    Never raises: failures are recorded on the returned CrawlRun instead.
    """
    run = CrawlRun.objects.create(
        query=query,
        query_name=query.name,
        spider_name=query.spider_name,
        trigger=trigger,
        status=CrawlRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    try:
        spider_cls = spiders.get_spider_by_name(query.spider_name)
        crawled_items = spider_cls({query.name: query.url}).run()

        new_items = _persist_and_diff(query, crawled_items, run)
        run.items_found_count = len(crawled_items)
        run.new_items_count = len(new_items)

        if new_items:
            notifications_config = {
                nc.notificator_name: nc.config for nc in query.notification_configs.filter(enabled=True)
            }
            scrape.send_notifications(notifications_config, query.name, new_items)

        run.status = CrawlRun.Status.SUCCESS
    except Exception as exc:  # pylint: disable=broad-except
        run.status = CrawlRun.Status.FAILED
        run.error_message = str(exc)
        logger.exception("Query run failed for %s", query)
    finally:
        run.finished_at = timezone.now()
        run.save()

    return run
