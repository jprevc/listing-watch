import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler_manager", "0010_backfill_notification_profiles"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="querynotificationconfig",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="querynotificationconfig",
            name="notificator_name",
        ),
        migrations.RemoveField(
            model_name="querynotificationconfig",
            name="config",
        ),
        migrations.RemoveField(
            model_name="querynotificationconfig",
            name="enabled",
        ),
        migrations.AlterField(
            model_name="querynotificationconfig",
            name="profile",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="query_attachments",
                to="crawler_manager.notificationprofile",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="querynotificationconfig",
            unique_together={("query", "profile")},
        ),
    ]
