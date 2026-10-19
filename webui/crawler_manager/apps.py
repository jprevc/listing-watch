import os
import sys

from django.apps import AppConfig

from listing_watch import registry

# Management commands where starting the ad-hoc "run now" scheduler would be pointless or
# actively unwanted (migrations, tests, and the dedicated `runscheduler` process, which has its
# own durable scheduler and must not also run this one).
_SKIP_ADHOC_SCHEDULER_COMMANDS = {"migrate", "makemigrations", "test", "runscheduler", "shell", "collectstatic"}


class CrawlerManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crawler_manager"

    def ready(self) -> None:
        # Discover the installed Plugins up front, so two Plugins registering the same Spider or
        # Notificator name stops the Core from starting instead of surfacing mid-request.
        registry.installed()

        # Connects the signal receivers that drop a detached Profile's pending Deliveries.
        from crawler_manager import delivery  # noqa: F401 pylint: disable=import-outside-toplevel,unused-import

        # Avoid starting the scheduler twice under the dev-server autoreloader, and skip it
        # entirely for management commands that don't serve requests.
        if os.environ.get("RUN_MAIN") != "true" and "runserver" in sys.argv:
            return
        if any(cmd in sys.argv for cmd in _SKIP_ADHOC_SCHEDULER_COMMANDS):
            return

        from crawler_manager import scheduling  # pylint: disable=import-outside-toplevel

        scheduling.get_adhoc_scheduler()
