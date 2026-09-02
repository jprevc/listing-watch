"""
Conversion between the "every N <unit>" schedule picker and the crontab expression that
Query.cron_schedule actually stores (and that scheduling.py hands to APScheduler's CronTrigger).
"""

from __future__ import annotations

import re

MINUTES = "minutes"
HOURS = "hours"
DAYS = "days"

UNIT_CHOICES = [(MINUTES, "Minutes"), (HOURS, "Hours"), (DAYS, "Days")]

# Inclusive bounds enforced on *new* simple-mode input. Expressed per unit rather than as a
# single cross-unit duration: 5 minutes is the floor (cron's minute field is 0-59, so anything
# finer isn't representable anyway), 30 days is the soft ceiling. Existing rows backfilled from
# a pre-existing cron_schedule (see the 0008 migration) are NOT re-validated against this -- it
# only gates values entered through the simple picker from here on.
BOUNDS: dict[str, tuple[int, int]] = {
    MINUTES: (5, 59),
    HOURS: (1, 23),
    DAYS: (1, 30),
}

_PATTERNS: dict[str, re.Pattern[str]] = {
    MINUTES: re.compile(r"^\*/(\d+) \* \* \* \*$"),
    HOURS: re.compile(r"^0 \*/(\d+) \* \* \*$"),
    DAYS: re.compile(r"^0 0 \*/(\d+) \* \*$"),
}


def to_cron(interval_value: int, interval_unit: str) -> str:
    """Renders an "every N <unit>" pair as the equivalent crontab expression."""
    if interval_unit == MINUTES:
        return f"*/{interval_value} * * * *"
    if interval_unit == HOURS:
        return f"0 */{interval_value} * * *"
    if interval_unit == DAYS:
        return f"0 0 */{interval_value} * *"
    raise ValueError(f"Unknown interval unit: {interval_unit!r}")


def from_cron(cron_schedule: str) -> tuple[int, str] | None:
    """
    Reverses `to_cron`: recognizes exactly the patterns it generates, so a hand-written cron
    expression that merely looks similar (e.g. a different day-of-week field) is correctly left
    unrecognized -- callers should fall back to advanced/raw display for those.
    """
    cron_schedule = cron_schedule.strip()
    for unit, pattern in _PATTERNS.items():
        match = pattern.match(cron_schedule)
        if match:
            return int(match.group(1)), unit
    return None
