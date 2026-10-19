from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from crawler_manager.failing import update_failing
from crawler_manager.models import CrawlRun, NotificationProfile, Query, QueryNotificationConfig
from listing_watch.notificators import Notificator

pytestmark = pytest.mark.django_db

START = datetime(2026, 10, 1, 8, 0, tzinfo=dt_timezone.utc)


class _Pigeon(Notificator):
    """Records every message it sends, as (subject, message)."""

    name = "pigeon"
    sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        self.sent.append((subject, message))


@pytest.fixture(name="sent")
def sent_fixture(installed_plugins) -> list[tuple[str, str]]:
    _Pigeon.sent = []
    installed_plugins(notificators={"pigeon": _Pigeon})
    return _Pigeon.sent


@pytest.fixture(name="query")
def query_fixture() -> Query:
    return Query.objects.create(name="cars", spider_name="cars", url="https://example.com")


def _attach(query: Query, name: str, notificator_name: str = "pigeon") -> NotificationProfile:
    profile = NotificationProfile.objects.create(name=name, notificator_name=notificator_name, config={})
    QueryNotificationConfig.objects.create(query=query, profile=profile)
    return profile


def _run(
    query: Query,
    status: CrawlRun.Status,
    error_message: str = "",
    trigger: CrawlRun.Trigger = CrawlRun.Trigger.SCHEDULED,
) -> CrawlRun:
    """Records a finished run of the Query, starting an hour after the one before it."""
    started_at = START + timedelta(hours=query.runs.count())
    if status == CrawlRun.Status.FAILED and not error_message:
        error_message = "site layout changed"
    return CrawlRun.objects.create(
        query=query,
        query_name=query.name,
        spider_name=query.spider_name,
        trigger=trigger,
        status=status,
        started_at=started_at,
        finished_at=started_at + timedelta(minutes=1),
        error_message=error_message,
    )


def _fail(query: Query, error_message: str = "", **kwargs) -> CrawlRun:
    run = _run(query, CrawlRun.Status.FAILED, error_message, **kwargs)
    update_failing(query, run)
    return run


def test_alerts_each_attached_profile_once_on_the_third_failed_run_in_a_row(query: Query, sent) -> None:
    _attach(query, "carrier")
    _attach(query, "backup")

    first = _fail(query)
    _fail(query)
    _fail(query, "HTTP 503")

    alert = (
        "cars is failing",
        "The last 3 runs of cars failed. It has been failing since 2026-10-01 10:00 CEST.\n\nLatest error:\nHTTP 503",
    )
    assert sent == [alert, alert]
    query.refresh_from_db()
    assert query.failing_since == first.started_at


def _succeed(query: Query, **kwargs) -> CrawlRun:
    run = _run(query, CrawlRun.Status.SUCCESS, **kwargs)
    update_failing(query, run)
    return run


def test_a_successful_run_while_failing_sends_one_working_again_message_and_clears_it(query: Query, sent) -> None:
    _attach(query, "carrier")
    for _ in range(3):
        _fail(query)
    sent.clear()

    _succeed(query)
    _succeed(query)

    assert sent == [
        (
            "cars is working again",
            "cars ran successfully at 2026-10-01 13:00 CEST, after failing since 2026-10-01 10:00 CEST.",
        )
    ]
    query.refresh_from_db()
    assert query.failing_since is None


def test_one_or_two_failed_runs_in_a_row_send_nothing(query: Query, sent) -> None:
    _attach(query, "carrier")

    _fail(query)
    _fail(query)

    assert sent == []
    query.refresh_from_db()
    assert query.failing_since is None


def test_a_success_breaks_the_streak(query: Query, sent) -> None:
    _attach(query, "carrier")
    _fail(query)
    _fail(query)
    _succeed(query)

    _fail(query)
    _fail(query)

    assert sent == []
    query.refresh_from_db()
    assert query.failing_since is None


def test_later_failed_runs_while_failing_send_no_further_alert(query: Query, sent) -> None:
    _attach(query, "carrier")
    for _ in range(3):
        _fail(query)
    sent.clear()

    _fail(query)
    _fail(query)

    assert sent == []


def test_a_successful_run_while_not_failing_sends_nothing(query: Query, sent) -> None:
    _attach(query, "carrier")

    _succeed(query)

    assert sent == []


def test_cancelled_runs_neither_count_toward_nor_break_the_streak(query: Query, sent) -> None:
    _attach(query, "carrier")
    first = _fail(query)
    update_failing(query, _run(query, CrawlRun.Status.CANCELLED))
    _fail(query)
    update_failing(query, _run(query, CrawlRun.Status.CANCELLED))

    assert sent == []

    _fail(query)

    assert [subject for subject, _ in sent] == ["cars is failing"]
    query.refresh_from_db()
    assert query.failing_since == first.started_at


def test_a_cancelled_run_while_failing_does_not_clear_it(query: Query, sent) -> None:
    _attach(query, "carrier")
    first = _fail(query)
    _fail(query)
    _fail(query)
    sent.clear()

    update_failing(query, _run(query, CrawlRun.Status.CANCELLED))

    assert sent == []
    query.refresh_from_db()
    assert query.failing_since == first.started_at


def test_unfinished_runs_do_not_count(query: Query, sent) -> None:
    _attach(query, "carrier")
    _fail(query)
    _run(query, CrawlRun.Status.RUNNING)
    _run(query, CrawlRun.Status.PENDING)

    _fail(query)

    assert sent == []


def test_manual_and_scheduled_runs_count_alike(query: Query, sent) -> None:
    _attach(query, "carrier")
    _fail(query, trigger=CrawlRun.Trigger.MANUAL)
    _fail(query, trigger=CrawlRun.Trigger.SCHEDULED)
    _fail(query, trigger=CrawlRun.Trigger.MANUAL)

    _succeed(query, trigger=CrawlRun.Trigger.MANUAL)

    assert [subject for subject, _ in sent] == ["cars is failing", "cars is working again"]


def test_a_query_already_failing_before_tracking_is_alerted_on_its_next_failed_run_since_its_first(
    query: Query, sent
) -> None:
    _attach(query, "carrier")
    _succeed(query)
    first = _run(query, CrawlRun.Status.FAILED)
    for _ in range(3):
        _run(query, CrawlRun.Status.FAILED)

    _fail(query)

    assert [subject for subject, _ in sent] == ["cars is failing"]
    query.refresh_from_db()
    assert query.failing_since == first.started_at


class _Smoke(Notificator):
    """Raises instead of sending."""

    name = "smoke"

    def send_text(self, subject: str, message: str) -> None:
        raise ConnectionError("no wind")


def test_a_profile_that_fails_to_send_does_not_stop_the_others_and_is_logged(
    query: Query, installed_plugins, caplog
) -> None:
    _Pigeon.sent = []
    installed_plugins(notificators={"pigeon": _Pigeon, "smoke": _Smoke})
    _attach(query, "signal", notificator_name="smoke")
    _attach(query, "carrier")

    for _ in range(3):
        _fail(query)

    assert [subject for subject, _ in _Pigeon.sent] == ["cars is failing"]
    assert "Notification Profile signal (smoke) failed to send 'cars is failing' about cars/cars" in caplog.text


def test_a_query_whose_profiles_all_fail_still_becomes_failing_and_recovers_without_retrying(
    query: Query, installed_plugins
) -> None:
    installed_plugins(notificators={"smoke": _Smoke})
    _attach(query, "signal", notificator_name="smoke")
    first = _fail(query)
    _fail(query)
    _fail(query)
    query.refresh_from_db()
    assert query.failing_since == first.started_at

    # A retry would raise again; it'd only show as the Query becoming un-Failing, which is checked below.
    _fail(query)
    _succeed(query)

    query.refresh_from_db()
    assert query.failing_since is None


def test_a_query_with_no_profiles_still_becomes_failing_and_recovers(query: Query, sent) -> None:
    first = _fail(query)
    _fail(query)
    _fail(query)
    query.refresh_from_db()
    assert query.failing_since == first.started_at

    _succeed(query)

    query.refresh_from_db()
    assert query.failing_since is None


def test_skips_an_unavailable_profile_rather_than_trying_it(query: Query, sent, caplog) -> None:
    _attach(query, "old smoke", notificator_name="smoke")
    _attach(query, "carrier")

    for _ in range(3):
        _fail(query)

    assert [subject for subject, _ in sent] == ["cars is failing"]
    assert "old smoke" not in caplog.text


def test_overlapping_runs_that_both_reach_the_threshold_alert_once(query: Query, sent) -> None:
    _attach(query, "carrier")
    _fail(query)
    _fail(query)
    # Each run holds the Query as it was when the run started, before either finished.
    mine, theirs = Query.objects.get(pk=query.pk), Query.objects.get(pk=query.pk)
    my_run, their_run = _run(query, CrawlRun.Status.FAILED), _run(query, CrawlRun.Status.FAILED)

    update_failing(mine, my_run)
    update_failing(theirs, their_run)

    assert [subject for subject, _ in sent] == ["cars is failing"]


def test_overlapping_successful_runs_while_failing_send_one_working_again_message(query: Query, sent) -> None:
    _attach(query, "carrier")
    for _ in range(3):
        _fail(query)
    sent.clear()
    mine, theirs = Query.objects.get(pk=query.pk), Query.objects.get(pk=query.pk)
    my_run, their_run = _run(query, CrawlRun.Status.SUCCESS), _run(query, CrawlRun.Status.SUCCESS)

    update_failing(mine, my_run)
    update_failing(theirs, their_run)

    assert [subject for subject, _ in sent] == ["cars is working again"]


def test_runs_count_in_the_order_they_finished_not_the_order_they_started(query: Query, sent) -> None:
    _attach(query, "carrier")
    # A long scheduled run starts first, three short manual runs fail while it crawls, then it succeeds.
    long_run = _run(query, CrawlRun.Status.RUNNING)
    for _ in range(3):
        _fail(query, trigger=CrawlRun.Trigger.MANUAL)
    long_run.status, long_run.finished_at = CrawlRun.Status.SUCCESS, START + timedelta(hours=5)
    long_run.save()
    update_failing(query, long_run)
    sent.clear()

    _fail(query)

    assert sent == []
    query.refresh_from_db()
    assert query.failing_since is None
