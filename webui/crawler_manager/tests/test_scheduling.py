import pytest
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from crawler_manager import scheduling
from crawler_manager.models import CrawlRun, Query
from listing_watch.spiders import Spider

pytestmark = pytest.mark.django_db


@pytest.fixture(name="scheduler")
def scheduler_fixture():
    sched = BackgroundScheduler(jobstores={"default": MemoryJobStore()})
    yield sched
    if sched.running:
        sched.shutdown()


def test_sync_all_jobs_adds_job_for_active_scheduled_query(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="cars", url="https://example.com", cron_schedule="*/15 * * * *", is_active=True
    )

    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is not None


def test_sync_all_jobs_skips_invalid_cron(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="cars", url="https://example.com", cron_schedule="not a cron", is_active=True
    )

    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is None


def test_sync_all_jobs_skips_query_without_schedule(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="cars", url="https://example.com", cron_schedule="", is_active=True
    )

    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is None


def test_sync_all_jobs_removes_job_for_deactivated_query(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="cars", url="https://example.com", cron_schedule="*/15 * * * *", is_active=True
    )
    scheduling.sync_all_jobs(scheduler)
    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is not None

    query.is_active = False
    query.save()
    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is None


def test_run_query_job_records_a_failed_run_for_an_unavailable_query_and_others_still_run(installed_plugins) -> None:
    class _BikesSpider(Spider):
        name = "bikes"

        def run(self, max_pages=None, should_stop=None):
            return [{"title": "bike", "url": "https://example.com/bike"}]

    installed_plugins(spiders={"bikes": _BikesSpider})
    unavailable = Query.objects.create(name="old_cars", spider_name="cars", url="https://example.com")
    available = Query.objects.create(name="new_bikes", spider_name="bikes", url="https://example.com")

    scheduling.run_query_job(unavailable.id, CrawlRun.Trigger.SCHEDULED)
    scheduling.run_query_job(available.id, CrawlRun.Trigger.SCHEDULED)

    failed_run = unavailable.runs.get()
    assert failed_run.status == CrawlRun.Status.FAILED
    assert failed_run.trigger == CrawlRun.Trigger.SCHEDULED
    assert failed_run.error_message == "No installed Plugin provides a Spider named 'cars'."
    assert available.runs.get().status == CrawlRun.Status.SUCCESS
