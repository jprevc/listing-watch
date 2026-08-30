import os
import sys

from django.apps import AppConfig

# Management commands where starting the ad-hoc "run now" scheduler would be pointless or
# actively unwanted (migrations, tests, and the dedicated `runscheduler` process, which has its
# own durable scheduler and must not also run this one).
_SKIP_ADHOC_SCHEDULER_COMMANDS = {"migrate", "makemigrations", "test", "runscheduler", "shell", "collectstatic"}


class CrawlerManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crawler_manager"

    def ready(self) -> None:
        # Avoid starting the scheduler twice under the dev-server autoreloader, and skip it
        # entirely for management commands that don't serve requests.
        if os.environ.get("RUN_MAIN") != "true" and "runserver" in sys.argv:
            return
        if any(cmd in sys.argv for cmd in _SKIP_ADHOC_SCHEDULER_COMMANDS):
            return

        from crawler_manager import scheduling  # pylint: disable=import-outside-toplevel

        scheduling.get_adhoc_scheduler()
