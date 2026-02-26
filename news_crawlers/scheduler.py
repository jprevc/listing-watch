from __future__ import annotations

import time
from typing import Callable

import schedule  # type: ignore
from news_crawlers import configuration


def _run_pending_func() -> None:
    """Run the scheduler loop indefinitely, executing pending jobs every second."""
    while True:
        schedule.run_pending()
        time.sleep(1)


def schedule_func(func: Callable[[], None], schedule_data: configuration.ScheduleConfig) -> None:
    """
    Schedule a callable to run at the given interval and start the scheduler loop.

    :param func: No-argument callable to run on the schedule (e.g. run_crawlers wrapper).
    :param schedule_data: Interval and unit (e.g. every 1 minute). Never returns; runs until interrupted.
    """
    schedule.every(int(schedule_data.every)).__getattribute__(  # pylint: disable=unnecessary-dunder-call
        schedule_data.units
    ).do(func)
    _run_pending_func()
