"""
The rules that decide how a Query run ends (see ADR-0002): its terminal status, plus the fields
recorded alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass

from crawler_manager.delivery import DeliveryOutcome
from crawler_manager.models import CrawlRun


@dataclass(frozen=True)
class RunOutcome:
    status: CrawlRun.Status
    error_message: str = ""
    pending_deliveries_count: int = 0
    delivery_errors: str = ""

    def record_on(self, run: CrawlRun) -> None:
        run.status = self.status
        run.error_message = self.error_message
        run.pending_deliveries_count = self.pending_deliveries_count
        run.delivery_errors = self.delivery_errors


def decide_run_outcome(
    *,
    crawl_error: Exception | None,
    stop_requested: bool,
    delivery: DeliveryOutcome | None = None,
    delivery_error: Exception | None = None,
) -> RunOutcome:
    """
    Decides how a run ends from what happened in it: whether the crawl raised (in which case
    nothing was delivered), whether a stop was requested, and what `deliver` reported or raised.

    Only a crawl failure fails a run. A finished crawl is `success`, or `cancelled` if a stop was
    requested, whatever happened to its Deliveries; those are recorded in the delivery fields.
    """
    if crawl_error is not None:
        return RunOutcome(status=CrawlRun.Status.FAILED, error_message=str(crawl_error))

    status = CrawlRun.Status.CANCELLED if stop_requested else CrawlRun.Status.SUCCESS
    if delivery_error is not None:
        return RunOutcome(status=status, delivery_errors=f"Delivery failed: {delivery_error}")
    assert delivery is not None, "a finished crawl either delivered or failed to"
    return RunOutcome(
        status=status,
        pending_deliveries_count=delivery.pending_count,
        delivery_errors="\n".join(f"{label}: {error}" for label, error in delivery.errors.items()),
    )
