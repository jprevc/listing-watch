# Backfills the new `user` FK (added in 0006) on all pre-existing Query/CrawlRun/FoundItem rows,
# which otherwise fall back to whoever's opened this deployment first-run. This instance only
# ever had one non-staff account ("jprevc") using it day to day, so that's the sole reasonable
# owner to backfill to -- adjust the username below before running this migration on a deployment
# where that assumption doesn't hold.

from django.conf import settings
from django.db import migrations

BACKFILL_USERNAME = "jprevc"


def backfill_owner(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    user = User.objects.filter(username=BACKFILL_USERNAME).first()
    if user is None:
        return

    Query = apps.get_model("crawler_manager", "Query")
    CrawlRun = apps.get_model("crawler_manager", "CrawlRun")
    FoundItem = apps.get_model("crawler_manager", "FoundItem")

    Query.objects.filter(user__isnull=True).update(user=user)
    CrawlRun.objects.filter(user__isnull=True).update(user=user)
    FoundItem.objects.filter(user__isnull=True).update(user=user)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crawler_manager", "0006_add_user_ownership"),
    ]

    operations = [
        migrations.RunPython(backfill_owner, noop_reverse),
    ]
