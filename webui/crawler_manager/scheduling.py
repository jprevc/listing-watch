"""
Two scheduler roles, kept deliberately separate to avoid double-scheduling across processes:

- A durable, cron-driven scheduler that only runs inside the `runscheduler` management command,
  backed by django-apscheduler's DjangoJobStore so jobs survive restarts.
- An ephemeral, in-memory scheduler used by the web process itself to run "Run now" requests as a
  non-blocking one-off job, so an HTTP request never blocks on a potentially slow scrape.
"""

from __future__ import annotations

import logging
import time

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.utils import timezone
from django_apscheduler.jobstores import DjangoJobStore

from crawler_manager.models import CrawlRun, Query

logger = logging.getLogger(__name__)

JOB_PREFIX = "query-"
SYNC_JOB_ID = "sync-all-jobs"


def run_query_job(query_id: int, trigger: str = CrawlRun.Trigger.SCHEDULED) -> None:
    # Local import: avoids importing services (and its listing_watch dependency chain) at module
    # load time for processes that only need the scheduler machinery, not the run logic itself.
    from crawler_manager import services  # pylint: disable=import-outside-toplevel

    query = Query.objects.filter(pk=query_id, is_active=True).first()
    if query is None:
        logger.info("Skipping run for query id %s: no longer active or deleted.", query_id)
        return
    services.run_query(query, trigger=trigger)


def sync_all_jobs(scheduler: BackgroundScheduler) -> None:
    """Reconciles APScheduler jobs with the current set of active, cron-scheduled queries."""
    active_job_ids = set()

    for query in Query.objects.filter(is_active=True).exclude(cron_schedule=""):
        job_id = f"{JOB_PREFIX}{query.id}"
        try:
            trigger = CronTrigger.from_crontab(query.cron_schedule, timezone=timezone.get_current_timezone())
        except ValueError:
            logger.warning("Invalid cron_schedule %r for query %s, skipping.", query.cron_schedule, query)
            continue

        active_job_ids.add(job_id)
        scheduler.add_job(
            run_query_job,
            trigger=trigger,
            args=[query.id, CrawlRun.Trigger.SCHEDULED],
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    for job in scheduler.get_jobs():
        if job.id.startswith(JOB_PREFIX) and job.id not in active_job_ids:
            scheduler.remove_job(job.id)


def run_scheduler_forever(sync_interval_seconds: int = 60) -> None:
    """Entry point for the `runscheduler` management command: blocks until interrupted."""
    from django_apscheduler.jobstores import register_events  # pylint: disable=import-outside-toplevel

    # Per-query jobs live in the durable "default" DjangoJobStore so they survive restarts. The
    # internal sync job itself must live in a plain in-memory store instead: it needs a reference
    # to the running `scheduler`, and APScheduler pickles job args for any persistent jobstore,
    # which fails because scheduler instances aren't picklable.
    scheduler = BackgroundScheduler(jobstores={"default": DjangoJobStore(), "internal": MemoryJobStore()})
    register_events(scheduler)

    scheduler.add_job(
        sync_all_jobs,
        args=[scheduler],
        trigger="interval",
        seconds=sync_interval_seconds,
        id=SYNC_JOB_ID,
        replace_existing=True,
        next_run_time=timezone.now(),
        jobstore="internal",
    )

    scheduler.start()
    logger.info("Scheduler started, syncing jobs every %ss.", sync_interval_seconds)
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


_adhoc_scheduler: BackgroundScheduler | None = None


def get_adhoc_scheduler() -> BackgroundScheduler:
    """Lazily starts a per-process, in-memory scheduler used only for one-off manual runs."""
    global _adhoc_scheduler  # pylint: disable=global-statement
    if _adhoc_scheduler is None:
        _adhoc_scheduler = BackgroundScheduler(jobstores={"default": MemoryJobStore()})
        _adhoc_scheduler.start()
    return _adhoc_scheduler


def trigger_manual_run(query: Query) -> str:
    """Schedules an immediate, non-blocking run of the given query. Returns the APScheduler job id."""
    job_id = f"manual-{query.id}-{int(time.time() * 1000)}"
    get_adhoc_scheduler().add_job(
        run_query_job,
        trigger="date",
        run_date=timezone.now(),
        args=[query.id, CrawlRun.Trigger.MANUAL],
        id=job_id,
    )
    return job_id
