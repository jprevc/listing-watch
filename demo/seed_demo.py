"""
Seeds the demo: a `demo` account with two Queries on the Demo Market (every new listing, every minute;
and bargains only, every 5 minutes), and an ntfy Notification Profile attached to both.
Safe to run on every start: anything already there is kept.

Run from the web UI's directory, after migrating: `python /demo/seed_demo.py`.
"""
from __future__ import annotations

import os
import sys

import django

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webui.settings")
django.setup()

# pylint: disable=wrong-import-position
from django.contrib.auth import get_user_model

from crawler_manager.models import NotificationProfile, Query, QueryNotificationConfig

MARKET_URL = os.environ.get("DEMO_MARKET_URL", "http://market.demo.test:8001/")
NTFY_SERVER = os.environ.get("DEMO_NTFY_SERVER", "http://ntfy.demo.test")
NTFY_TOPIC = os.environ.get("DEMO_NTFY_TOPIC", "listing-watch-demo")


def seed() -> None:
    user, created = get_user_model().objects.get_or_create(username="demo")
    if created:
        user.set_password("demo")
        user.save()

    profile, _ = NotificationProfile.objects.get_or_create(
        user=user,
        name="Demo ntfy",
        defaults={
            "notificator_name": "ntfy",
            "config": {"topic": NTFY_TOPIC, "server": NTFY_SERVER, "tags": "shopping_cart"},
            "is_default": True,
        },
    )
    for name, cron_schedule, spider_config in (
        ("Demo Market", "* * * * *", {}),
        ("Bargains under €100", "*/5 * * * *", {"max_price": "100"}),
    ):
        query, _ = Query.objects.get_or_create(
            user=user,
            spider_name="demo-market",
            name=name,
            defaults={
                "url": MARKET_URL,
                "spider_config": spider_config,
                "schedule_mode": Query.ScheduleMode.ADVANCED,
                "cron_schedule": cron_schedule,
            },
        )
        QueryNotificationConfig.objects.get_or_create(
            query=query,
            profile=profile,
            defaults={"message_body_format": "{title} — {price}, {location}\n{url}"},
        )


if __name__ == "__main__":
    seed()
    print("Demo seeded: sign in as demo / demo.")
