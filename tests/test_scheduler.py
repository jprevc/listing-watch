import pathlib
import time

import schedule  # type: ignore

from news_crawlers import scheduler


def write_line_to_file(file_path):
    with open(file_path, "a+", encoding="utf8") as file:
        file.write("new line\n")


def test_schedule(tmp_path: pathlib.Path, monkeypatch):
    tmp_file_path = tmp_path / "tmp_file.txt"

    # mock "_run_pending_func", otherwise it would be stuck in infinite loop
    def mock_run_pending():
        start_time = time.time()
        while time.time() - start_time < 2.1:
            schedule.run_pending()

    monkeypatch.setattr(scheduler, "_run_pending_func", mock_run_pending)

    sch_data = scheduler.ScheduleData(every=1, units="seconds")

    scheduler.schedule_func(lambda: write_line_to_file(tmp_file_path), sch_data)

    with open(tmp_file_path, encoding="utf8") as file:
        lines = file.readlines()
        assert lines == ["new line\n"] * 2
