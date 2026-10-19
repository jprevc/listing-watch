import pytest

from crawler_manager.delivery import DeliveryOutcome
from crawler_manager.models import CrawlRun
from crawler_manager.run_outcome import RunOutcome, decide_run_outcome


def test_a_finished_crawl_with_no_stop_succeeds_and_records_its_delivery() -> None:
    outcome = decide_run_outcome(
        crawl_error=None, stop_requested=False, delivery=DeliveryOutcome(pending_count=0, errors={})
    )

    assert outcome == RunOutcome(status=CrawlRun.Status.SUCCESS)


def test_a_crawl_that_raised_fails_with_its_error_and_records_no_delivery() -> None:
    outcome = decide_run_outcome(crawl_error=RuntimeError("site layout changed"), stop_requested=False)

    assert outcome == RunOutcome(status=CrawlRun.Status.FAILED, error_message="site layout changed")


def test_pending_deliveries_and_delivery_errors_are_recorded_on_a_run_that_still_succeeds() -> None:
    delivery = DeliveryOutcome(pending_count=3, errors={"carrier (pigeon)": "no wind", "old smoke (smoke)": "gone"})

    outcome = decide_run_outcome(crawl_error=None, stop_requested=False, delivery=delivery)

    assert outcome == RunOutcome(
        status=CrawlRun.Status.SUCCESS,
        pending_deliveries_count=3,
        delivery_errors="carrier (pigeon): no wind\nold smoke (smoke): gone",
    )


def test_a_finished_crawl_that_was_asked_to_stop_is_cancelled_even_with_delivery_errors() -> None:
    delivery = DeliveryOutcome(pending_count=1, errors={"carrier (pigeon)": "no wind"})

    outcome = decide_run_outcome(crawl_error=None, stop_requested=True, delivery=delivery)

    assert outcome == RunOutcome(
        status=CrawlRun.Status.CANCELLED, pending_deliveries_count=1, delivery_errors="carrier (pigeon): no wind"
    )


@pytest.mark.parametrize(
    ("stop_requested", "status"), [(False, CrawlRun.Status.SUCCESS), (True, CrawlRun.Status.CANCELLED)]
)
def test_deliver_raising_never_fails_the_finished_crawl(stop_requested: bool, status: CrawlRun.Status) -> None:
    outcome = decide_run_outcome(
        crawl_error=None, stop_requested=stop_requested, delivery_error=ConnectionError("database is locked")
    )

    assert outcome == RunOutcome(status=status, delivery_errors="Delivery failed: database is locked")


def test_a_crawl_that_raised_fails_even_when_a_stop_was_requested() -> None:
    outcome = decide_run_outcome(crawl_error=RuntimeError("timed out"), stop_requested=True)

    assert outcome == RunOutcome(status=CrawlRun.Status.FAILED, error_message="timed out")
