import pytest
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from crawler_manager import scheduling
from crawler_manager.models import Query

pytestmark = pytest.mark.django_db


@pytest.fixture(name="scheduler")
def scheduler_fixture():
    sched = BackgroundScheduler(jobstores={"default": MemoryJobStore()})
    yield sched
    if sched.running:
        sched.shutdown()


def test_sync_all_jobs_adds_job_for_active_scheduled_query(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="example", url="https://example.com", cron_schedule="*/15 * * * *", is_active=True
    )

    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is not None


def test_sync_all_jobs_skips_invalid_cron(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="example", url="https://example.com", cron_schedule="not a cron", is_active=True
    )

    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is None


def test_sync_all_jobs_skips_query_without_schedule(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="example", url="https://example.com", cron_schedule="", is_active=True
    )

    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is None


def test_sync_all_jobs_removes_job_for_deactivated_query(scheduler) -> None:
    query = Query.objects.create(
        name="q1", spider_name="example", url="https://example.com", cron_schedule="*/15 * * * *", is_active=True
    )
    scheduling.sync_all_jobs(scheduler)
    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is not None

    query.is_active = False
    query.save()
    scheduling.sync_all_jobs(scheduler)

    assert scheduler.get_job(f"{scheduling.JOB_PREFIX}{query.id}") is None
