import time

import schedule  # type: ignore


def _run_pending_func():
    while True:
        schedule.run_pending()
        time.sleep(1)


def schedule_func(func, every: int = 1, units: str = "minutes"):
    schedule.every(int(every)).__getattribute__(units).do(func)  # pylint: disable=unnecessary-dunder-call
    _run_pending_func()
