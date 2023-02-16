import time

import schedule  # type: ignore
from news_crawlers import configuration


def _run_pending_func():
    while True:
        schedule.run_pending()
        time.sleep(1)


def schedule_func(func, schedule_data: configuration.ScheduleConfig):
    schedule.every(int(schedule_data.every)).__getattribute__(  # pylint: disable=unnecessary-dunder-call
        schedule_data.units
    ).do(func)
    _run_pending_func()
