"""
Failing: alerts a Query's Notification Profiles once when the Query's crawl has failed on each of
its last few runs, and once more when a run's crawl succeeds again.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.utils import timezone

from listing_watch import registry

from crawler_manager.models import CrawlRun, Query

logger = logging.getLogger(__name__)

# How many finished runs in a row, not counting cancelled ones, must fail for a Query to become Failing.
FAILING_AFTER = 3


def update_failing(query: Query, run: CrawlRun) -> None:
    """
    Updates whether the Query is Failing after its `run` finished (and was saved), sending the alert
    when it becomes Failing and the recovery message when it stops being Failing.
    """
    if run.status == CrawlRun.Status.FAILED:
        _on_failed(query, run)
    elif run.status == CrawlRun.Status.SUCCESS:
        _on_success(query, run)


def _on_failed(query: Query, run: CrawlRun) -> None:
    since = _streak_start(query)
    if since is None:
        return
    # Runs of the same Query can overlap (e.g. "Run now" during a scheduled run). Setting it in a
    # single conditional UPDATE means only one of them sends the alert.
    if not Query.objects.filter(pk=query.pk, failing_since__isnull=True).update(failing_since=since):
        return
    query.failing_since = since
    _send(
        query,
        f"{query.name} is failing",
        f"The last {FAILING_AFTER} runs of {query.name} failed. It has been failing since {_format(since)}."
        f"\n\nLatest error:\n{run.error_message}",
    )


def _on_success(query: Query, run: CrawlRun) -> None:
    since = Query.objects.filter(pk=query.pk).values_list("failing_since", flat=True).get()
    if since is None:
        return
    # As in `_on_failed`: matching on the value just read means only one overlapping run clears it.
    if not Query.objects.filter(pk=query.pk, failing_since=since).update(failing_since=None):
        return
    query.failing_since = None
    assert run.started_at is not None, "a finished run has started"
    _send(
        query,
        f"{query.name} is working again",
        f"{query.name} ran successfully at {_format(run.started_at)}, after failing since {_format(since)}.",
    )


def _streak_start(query: Query) -> datetime | None:
    """The `started_at` of the first failed run in the current streak, if it has reached FAILING_AFTER runs."""
    # Cancelled runs neither extend nor break the streak, and unfinished ones don't count yet.
    last_success = query.runs.filter(status=CrawlRun.Status.SUCCESS).order_by("-started_at").first()
    streak = query.runs.filter(status=CrawlRun.Status.FAILED)
    if last_success is not None:
        streak = streak.filter(started_at__gt=last_success.started_at)
    started = list(streak.order_by("started_at").values_list("started_at", flat=True))
    return started[0] if len(started) >= FAILING_AFTER else None


def _send(query: Query, subject: str, message: str) -> None:
    for attachment in query.notification_configs.select_related("profile"):
        profile = attachment.profile
        if profile.unavailable_reason:
            continue
        # One Profile failing must not stop the others. Nothing retries: the Query's state stands either way.
        try:
            registry.installed().get_notificator(profile.notificator_name)(profile.config).send_text(subject, message)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Notification Profile %s failed to send %r about %s", profile, subject, query)


def _format(moment: datetime) -> str:
    return timezone.localtime(moment).strftime("%Y-%m-%d %H:%M %Z")
