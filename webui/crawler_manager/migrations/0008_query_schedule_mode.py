import re

from django.db import migrations, models

# Deliberately duplicated from schedule_utils.py rather than imported: migrations must keep
# working the same way regardless of later changes to that module.
_PATTERNS = [
    ("minutes", re.compile(r"^\*/(\d+) \* \* \* \*$")),
    ("hours", re.compile(r"^0 \*/(\d+) \* \* \*$")),
    ("days", re.compile(r"^0 0 \*/(\d+) \* \*$")),
]


def _backfill_schedule_mode(apps, schema_editor):
    Query = apps.get_model("crawler_manager", "Query")
    for query in Query.objects.all():
        cron = (query.cron_schedule or "").strip()

        if not cron:
            query.schedule_mode = "manual"
            query.interval_value = None
            query.interval_unit = ""
        else:
            matched = None
            for unit, pattern in _PATTERNS:
                match = pattern.match(cron)
                if match:
                    matched = (unit, int(match.group(1)))
                    break

            if matched:
                unit, value = matched
                query.schedule_mode = "simple"
                query.interval_value = value
                query.interval_unit = unit
            else:
                query.schedule_mode = "advanced"
                query.interval_value = None
                query.interval_unit = ""

        query.save(update_fields=["schedule_mode", "interval_value", "interval_unit"])


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crawler_manager", "0007_backfill_user_ownership"),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="schedule_mode",
            field=models.CharField(
                choices=[
                    ("manual", "Manual only"),
                    ("simple", "Every N minutes/hours/days"),
                    ("advanced", "Custom cron expression"),
                ],
                default="simple",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="query",
            name="interval_value",
            field=models.PositiveIntegerField(blank=True, help_text="Used when schedule_mode is 'simple'.", null=True),
        ),
        migrations.AddField(
            model_name="query",
            name="interval_unit",
            field=models.CharField(
                blank=True,
                choices=[("minutes", "Minutes"), ("hours", "Hours"), ("days", "Days")],
                help_text="Used when schedule_mode is 'simple'.",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="query",
            name="cron_schedule",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Standard 5-field crontab expression (e.g. '*/15 * * * *'). Only used directly "
                    "when schedule_mode is 'advanced' -- otherwise it's derived automatically from "
                    "interval_value/interval_unit, or left blank for manual-only."
                ),
                max_length=64,
            ),
        ),
        migrations.RunPython(_backfill_schedule_mode, _noop_reverse),
    ]
