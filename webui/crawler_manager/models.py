"""
Database models backing the web UI: user-configured queries (which URL to crawl with which
spider, on which schedule, with which notifications), plus the found items and run history
that replace the old JSON-file cache.
"""

from __future__ import annotations

from django.db import models

from crawler_manager.registry import available_notificator_choices, available_spider_choices


class Query(models.Model):
    """A single crawl target: a name + URL to run through a given spider, on an optional schedule."""

    name = models.CharField(max_length=255, help_text="Query name, passed to the spider (e.g. used in messages).")
    spider_name = models.CharField(max_length=64, choices=available_spider_choices)
    url = models.URLField(max_length=2000)
    cron_schedule = models.CharField(
        max_length=64,
        blank=True,
        help_text="Standard 5-field crontab expression (e.g. '*/15 * * * *'). Leave blank to only run manually.",
    )
    max_pages = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Max pagination pages to crawl on runs after the first (only applies to spiders that "
            "paginate). The first successful run for a query always crawls every page, to build "
            "up the full result history. Leave blank for unlimited on every run."
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("spider_name", "name")]
        ordering = ["spider_name", "name"]

    def __str__(self) -> str:
        return f"{self.spider_name}/{self.name}"


class QueryNotificationConfig(models.Model):
    """One notificator (email/pushover/ntfy/...) configured for a given query."""

    query = models.ForeignKey(Query, related_name="notification_configs", on_delete=models.CASCADE)
    notificator_name = models.CharField(max_length=64, choices=available_notificator_choices)
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Notificator configuration, e.g. message_body_format, send_separately, recipients.",
    )
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("query", "notificator_name")]

    def __str__(self) -> str:
        return f"{self.query} -> {self.notificator_name}"


class CrawlRun(models.Model):
    """A single execution of a query, either scheduled or manually triggered."""

    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    query = models.ForeignKey(Query, null=True, blank=True, on_delete=models.SET_NULL, related_name="runs")
    # Denormalized so history survives query deletion/renaming.
    query_name = models.CharField(max_length=255)
    spider_name = models.CharField(max_length=64)

    trigger = models.CharField(max_length=16, choices=Trigger.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    items_found_count = models.PositiveIntegerField(default=0)
    new_items_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.query_name} ({self.spider_name}) @ {self.started_at}: {self.status}"


class FoundItem(models.Model):
    """A single item scraped by a spider, deduplicated by content hash per spider/query."""

    run = models.ForeignKey(CrawlRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    # Updated on every run that (re-)encounters this item, not just the run that first created
    # it -- lets the "Found" count on a run (which includes already-seen items, unlike "New")
    # link back to the actual items that made it up.
    last_seen_run = models.ForeignKey(CrawlRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    query = models.ForeignKey(Query, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    # Denormalized so items survive query deletion/renaming.
    query_name = models.CharField(max_length=255)
    spider_name = models.CharField(max_length=64)

    title = models.CharField(max_length=500, blank=True)
    url = models.URLField(max_length=2000, blank=True)
    price = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(help_text="Full raw item dict as returned by the spider.")

    content_hash = models.CharField(max_length=64, db_index=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("spider_name", "query_name", "content_hash")]
        ordering = ["-first_seen_at"]

    def __str__(self) -> str:
        return self.title or self.url or f"item #{self.pk}"
