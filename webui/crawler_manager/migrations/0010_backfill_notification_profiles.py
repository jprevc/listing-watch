# Converts each existing QueryNotificationConfig row's inline (notificator_name, config) into a
# reusable NotificationProfile, owned by that query's user:
#   - Identical configs (same user, same notificator type, same config values once
#     message_body_format/send_separately are stripped out) are merged into a single shared
#     profile referenced by every query that had that duplicate, rather than one profile per row.
#   - Rows that were `enabled=False` are dropped rather than kept as an attachment: the new model
#     has no "enabled" flag, so "off" is now represented by not attaching a profile at all. The
#     underlying settings are still preserved as an (unattached) profile in case they're wanted
#     again later.
# `send_separately` is dropped entirely (see forms.py/notificators.py -- it's never used in
# practice, so the config-driven flag isn't worth preserving).

from django.conf import settings
from django.db import migrations

DEFAULT_MESSAGE_BODY_FORMAT = "Query: {query}\nTitle: {title}\nURL: {url}\nPrice: {price}"


def _unique_profile_name(names_by_user, user_id, notificator_name):
    used = names_by_user.setdefault(user_id, set())
    base = f"Migrated {notificator_name} profile"
    name = base
    suffix = 2
    while name in used:
        name = f"{base} {suffix}"
        suffix += 1
    used.add(name)
    return name


def backfill_notification_profiles(apps, schema_editor):
    QueryNotificationConfig = apps.get_model("crawler_manager", "QueryNotificationConfig")
    NotificationProfile = apps.get_model("crawler_manager", "NotificationProfile")

    profiles_by_key = {}
    names_by_user = {}

    for row in QueryNotificationConfig.objects.select_related("query").order_by("pk"):
        user_id = row.query.user_id
        config = dict(row.config or {})
        message_body_format = config.pop("message_body_format", None) or DEFAULT_MESSAGE_BODY_FORMAT
        config.pop("send_separately", None)

        key = (user_id, row.notificator_name, tuple(sorted(config.items())))
        profile = profiles_by_key.get(key)
        if profile is None:
            profile = NotificationProfile.objects.create(
                user_id=user_id,
                name=_unique_profile_name(names_by_user, user_id, row.notificator_name),
                notificator_name=row.notificator_name,
                config=config,
            )
            profiles_by_key[key] = profile

        if row.enabled:
            row.profile_id = profile.pk
            row.message_body_format = message_body_format
            row.save(update_fields=["profile", "message_body_format"])
        else:
            row.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("crawler_manager", "0009_add_notification_profiles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(backfill_notification_profiles, noop_reverse),
    ]
