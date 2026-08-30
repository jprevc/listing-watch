"""
One-time import of the legacy news_crawlers.yaml config into the database.
"""

import pathlib

import yaml
from django.core.management.base import BaseCommand, CommandError

from news_crawlers import configuration as nc_configuration

from crawler_manager.models import Query, QueryNotificationConfig

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


class Command(BaseCommand):
    help = "Imports queries and notification config from a legacy news_crawlers.yaml file into the database."

    def add_arguments(self, parser):
        parser.add_argument("--config", type=pathlib.Path, default=None, help="Path to news_crawlers.yaml.")
        parser.add_argument("--dry-run", action="store_true", help="Print what would be imported, without writing.")

    def handle(self, *args, **options):
        config_path = nc_configuration.find_config(options["config"])
        with open(config_path, encoding="utf8") as file:
            raw_config = yaml.safe_load(file) or {}

        try:
            config = nc_configuration.NewsCrawlersConfig(**raw_config)
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
                    defaults={"url": url, "cron_schedule": default_cron, "is_active": True},
                )
                self.stdout.write(f"{'Created' if created else 'Already exists'}: {query}")

                for notificator_name, notificator_config in spider_config.notifications.items():
                    _, notif_created = QueryNotificationConfig.objects.get_or_create(
                        query=query,
                        notificator_name=notificator_name,
                        defaults={"config": notificator_config, "enabled": True},
                    )
                    if notif_created:
                        self.stdout.write(f"  + notification config: {notificator_name}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete, no changes written."))
