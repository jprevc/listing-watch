import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import crawler_manager.registry


class Migration(migrations.Migration):

    dependencies = [
        ("crawler_manager", "0008_query_schedule_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                (
                    "notificator_name",
                    models.CharField(choices=crawler_manager.registry.available_notificator_choices, max_length=64),
                ),
                (
                    "config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Notificator-specific configuration, e.g. topic, token, recipients.",
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False, help_text="Auto-attached (pre-selected) when this user adds a new query."
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notification_profiles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["notificator_name", "name"],
                "unique_together": {("user", "name")},
            },
        ),
        migrations.AddConstraint(
            model_name="notificationprofile",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_default", True)),
                fields=("user", "notificator_name"),
                name="unique_default_profile_per_user_and_type",
            ),
        ),
        migrations.AddField(
            model_name="querynotificationconfig",
            name="profile",
            # Temporarily nullable: existing rows get a profile via the data migration that
            # follows (0010) before 0011 makes this required and drops the old inline fields.
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="query_attachments",
                to="crawler_manager.notificationprofile",
            ),
        ),
        migrations.AddField(
            model_name="querynotificationconfig",
            name="message_body_format",
            field=models.TextField(
                default="Query: {query}\nTitle: {title}\nURL: {url}\nPrice: {price}",
                help_text="str.format() template.",
            ),
        ),
    ]
