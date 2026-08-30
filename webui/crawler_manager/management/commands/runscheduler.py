from django.core.management.base import BaseCommand

from crawler_manager import scheduling


class Command(BaseCommand):
    help = "Runs the durable, cron-driven scheduler that periodically triggers active queries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-interval",
            type=int,
            default=60,
            help="Seconds between reconciling scheduled jobs with the current set of active queries.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting scheduler..."))
        scheduling.run_scheduler_forever(sync_interval_seconds=options["sync_interval"])
