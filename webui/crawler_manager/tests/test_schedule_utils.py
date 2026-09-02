import pytest

from crawler_manager import schedule_utils


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (15, schedule_utils.MINUTES, "*/15 * * * *"),
        (5, schedule_utils.HOURS, "0 */5 * * *"),
        (2, schedule_utils.DAYS, "0 0 */2 * *"),
    ],
)
def test_to_cron(value, unit, expected) -> None:
    assert schedule_utils.to_cron(value, unit) == expected


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        (15, schedule_utils.MINUTES),
        (5, schedule_utils.HOURS),
        (2, schedule_utils.DAYS),
    ],
)
def test_from_cron_reverses_to_cron(value, unit) -> None:
    assert schedule_utils.from_cron(schedule_utils.to_cron(value, unit)) == (value, unit)


def test_from_cron_does_not_match_custom_cron() -> None:
    assert schedule_utils.from_cron("0 3 * * MON") is None


def test_from_cron_blank_does_not_match() -> None:
    assert schedule_utils.from_cron("") is None
