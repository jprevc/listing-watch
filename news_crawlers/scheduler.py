import time

import schedule  # type: ignore
import pydantic


class ScheduleData(pydantic.BaseModel):
    every: int = 1
    units: str = "minutes"


def _run_pending_func():
    while True:
        schedule.run_pending()
        time.sleep(1)


def schedule_func(func, schedule_data: ScheduleData):
    schedule.every(int(schedule_data.every)).__getattribute__(  # pylint: disable=unnecessary-dunder-call
        schedule_data.units
    ).do(func)
    _run_pending_func()
