"""
One-time import of the legacy listing_watch.yaml config into the database.
"""

import pathlib

import yaml
from django.core.management.base import BaseCommand, CommandError

from listing_watch import configuration as nc_configuration

from crawler_manager import schedule_utils
from crawler_manager.models import DEFAULT_MESSAGE_BODY_FORMAT, NotificationProfile, Query, QueryNotificationConfig

KNOWN_SPIDER_NAMES = {"example", "example"}


def _schedule_to_cron(schedule: nc_configuration.ScheduleConfig | None) -> str:
    """
    Best-effort conversion of the legacy every/units schedule to a crontab expression.
    Not every interval is representable in standard 5-field cron; unsupported cases are left
    blank (manual-only) so the user can set an equivalent schedule by hand in the UI.
    """
    if schedule is None:
        return ""

    every, units = schedule.every, schedule.units
    if units == "minutes" and 1 <= every <= 59:
        return f"*/{every} * * * *"
    if units == "hours" and 1 <= every <= 23:
        return f"0 */{every} * * *"
    if units == "days" and every >= 1:
        return f"0 0 */{every} * *"
    if units == "weeks" and every == 1:
        return "0 0 * * 0"
    return ""


def _schedule_fields(cron: str) -> dict[str, object]:
    """Query field values consistent with a given (possibly blank) crontab expression."""
    if not cron:
        return {"schedule_mode": Query.ScheduleMode.MANUAL}

    parsed = schedule_utils.from_cron(cron)
    if parsed is not None:
        value, unit = parsed
        return {"schedule_mode": Query.ScheduleMode.SIMPLE, "interval_value": value, "interval_unit": unit}

    return {"schedule_mode": Query.ScheduleMode.ADVANCED, "cron_schedule": cron}


class Command(BaseCommand):
    help = "Imports queries and notification config from a legacy listing_watch.yaml file into the database."

    def add_arguments(self, parser):
        parser.add_argument("--config", type=pathlib.Path, default=None, help="Path to listing_watch.yaml.")
        parser.add_argument("--dry-run", action="store_true", help="Print what would be imported, without writing.")

    def handle(self, *args, **options):
        config_path = nc_configuration.find_config(options["config"])
        with open(config_path, encoding="utf8") as file:
            raw_config = yaml.safe_load(file) or {}

        try:
            config = nc_configuration.ListingWatchConfig(**raw_config)
        except Exception as exc:  # pylint: disable=broad-except
            raise CommandError(f"Could not parse {config_path}: {exc}") from exc

        default_cron = _schedule_to_cron(config.schedule)
        dry_run = options["dry_run"]

        for spider_name, spider_config in config.spiders.items():
            if spider_name not in KNOWN_SPIDER_NAMES:
                self.stderr.write(
                    self.style.WARNING(f"Skipping unrecognized spider '{spider_name}' (no such spider implemented).")
                )
                continue

            for query_name, url in spider_config.urls.items():
                if dry_run:
                    self.stdout.write(f"Would import {spider_name}/{query_name} -> {url}")
                    continue

                query, created = Query.objects.get_or_create(
                    spider_name=spider_name,
                    name=query_name,
                    defaults={"url": url, "is_active": True, **_schedule_fields(default_cron)},
                )
                self.stdout.write(f"{'Created' if created else 'Already exists'}: {query}")

                for notificator_name, notificator_config in spider_config.notifications.items():
                    config = dict(notificator_config)
                    message_body_format = config.pop("message_body_format", None) or DEFAULT_MESSAGE_BODY_FORMAT
                    # Dropped entirely (see forms.py/notificators.py): never used in practice.
                    config.pop("send_separately", None)

                    # No --user option on this legacy one-time import (queries above are likewise
                    # created without one): profiles land owned by nobody, same as the query they
                    # attach to, until an admin reassigns both by hand.
                    profile, _ = NotificationProfile.objects.get_or_create(
                        user=None,
                        name=f"{spider_name}/{query_name} ({notificator_name})",
                        defaults={"notificator_name": notificator_name, "config": config},
                    )
                    _, notif_created = QueryNotificationConfig.objects.get_or_create(
                        query=query,
                        profile=profile,
                        defaults={"message_body_format": message_body_format},
                    )
                    if notif_created:
                        self.stdout.write(f"  + notification config: {notificator_name}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete, no changes written."))
