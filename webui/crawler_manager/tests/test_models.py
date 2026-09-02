import pytest
from django.db import IntegrityError

from crawler_manager.models import FoundItem, Query

pytestmark = pytest.mark.django_db


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="test_query", spider_name="example", url="https://example.com")


def test_query_str(query: Query) -> None:
    assert str(query) == "example/test_query"


def test_query_save_derives_cron_schedule_in_simple_mode(query: Query) -> None:
    query.schedule_mode = Query.ScheduleMode.SIMPLE
    query.interval_value = 15
    query.interval_unit = "minutes"
    query.save()

    assert query.cron_schedule == "*/15 * * * *"


def test_query_save_blanks_cron_schedule_in_manual_mode(query: Query) -> None:
    query.schedule_mode = Query.ScheduleMode.ADVANCED
    query.cron_schedule = "0 3 * * *"
    query.save()

    query.schedule_mode = Query.ScheduleMode.MANUAL
    query.save()

    assert query.cron_schedule == ""


def test_query_save_leaves_cron_schedule_alone_in_advanced_mode(query: Query) -> None:
    query.schedule_mode = Query.ScheduleMode.ADVANCED
    query.cron_schedule = "0 3 * * MON"
    query.save()

    assert query.cron_schedule == "0 3 * * MON"


def test_schedule_display_manual(query: Query) -> None:
    query.schedule_mode = Query.ScheduleMode.MANUAL
    assert query.schedule_display == "Manual only"


def test_schedule_display_simple_pluralizes_by_value() -> None:
    query = Query(schedule_mode=Query.ScheduleMode.SIMPLE, interval_value=1, interval_unit="minutes")
    assert query.schedule_display == "Every 1 minute"

    query.interval_value = 15
    assert query.schedule_display == "Every 15 minutes"


def test_schedule_display_advanced_shows_raw_cron(query: Query) -> None:
    query.schedule_mode = Query.ScheduleMode.ADVANCED
    query.cron_schedule = "0 3 * * MON"
    assert query.schedule_display == "0 3 * * MON"


def test_found_item_dedup_constraint(query: Query) -> None:
    FoundItem.objects.create(
        query=query,
        query_name=query.name,
        spider_name=query.spider_name,
        payload={"title": "a"},
        content_hash="hash1",
    )
    with pytest.raises(IntegrityError):
        FoundItem.objects.create(
            query=query,
            query_name=query.name,
            spider_name=query.spider_name,
            payload={"title": "a"},
            content_hash="hash1",
        )
