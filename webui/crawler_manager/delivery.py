"""
Delivery: sends a Query's Items to the Notification Profiles attached to it, keeping one Delivery
per Item and Profile so an Item a Profile didn't accept is retried on later runs (see ADR-0002).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from listing_watch import registry

from crawler_manager.models import Delivery, FoundItem, Query, QueryNotificationConfig

logger = logging.getLogger(__name__)

# How long after its Item was found a Delivery may stay pending, so a Profile fixed weeks later
# isn't flooded with stale listings.
EXPIRE_AFTER = timedelta(days=7)


@dataclass(frozen=True)
class DeliveryOutcome:
    # Pending Deliveries left for the Query.
    pending_count: int
    # Notification Profile label -> why its Deliveries are still pending.
    errors: dict[str, str]


def deliver(query: Query, new_items: list[FoundItem]) -> DeliveryOutcome:
    """
    Records a pending Delivery of each new Item to each Profile attached to the Query, then sends
    every Profile all of its pending Deliveries for the Query, in one message.
    """
    attachments = list(query.notification_configs.select_related("profile"))
    Delivery.objects.bulk_create(
        [Delivery(item=item, profile=attachment.profile) for item in new_items for attachment in attachments]
    )
    pending = Delivery.objects.filter(item__query=query, status=Delivery.Status.PENDING)
    # The receivers below already drop these when a Profile is detached; this also catches
    # detachments that bypass signals (e.g. `QuerySet.update()`).
    pending.exclude(profile__in=[attachment.profile for attachment in attachments]).delete()
    pending.filter(item__first_seen_at__lt=timezone.now() - EXPIRE_AFTER).update(status=Delivery.Status.EXPIRED)

    errors: dict[str, str] = {}
    for attachment in attachments:
        profile = attachment.profile
        # Not worth trying: its Deliveries stay pending until a Plugin provides it again, or they expire.
        if profile.unavailable_reason:
            errors[str(profile)] = f"Skipped (Unavailable): {profile.unavailable_reason}"
            continue
        # Older Items first, then this run's, each in the order they were found.
        deliveries = list(
            pending.filter(profile=profile).select_related("item").order_by("item__first_seen_at", "item__pk")
        )
        if not deliveries:
            continue
        # The Core, not the Spider, names the Query: an Item only has to carry a title and a URL,
        # but Notificators group Items under a "Query: ..." header read from each Item's `query`.
        items = [{**delivery.item.payload, "query": query.name} for delivery in deliveries]
        # One Profile failing (e.g. bad credentials) must not stop the others from sending.
        try:
            notificator = registry.installed().get_notificator(profile.notificator_name)(profile.config)
            notificator.send_items(f"{query.name} news", items, attachment.message_body_format)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Notification Profile %s failed to send %s's Items", profile, query)
            errors[str(profile)] = str(exc)
            continue
        pending.filter(pk__in=[delivery.pk for delivery in deliveries]).update(
            status=Delivery.Status.DELIVERED, delivered_at=timezone.now()
        )

    return DeliveryOutcome(pending_count=pending.count(), errors=errors)


# Detaching a Profile drops its pending Deliveries for that Query right away, not just on the
# Query's next run, so re-attaching it before then doesn't bring them back. Deleting a Query
# deletes its attachments, so this also drops the Query's pending Deliveries; the delivered and
# expired ones stay as history.


@receiver(pre_save, sender=QueryNotificationConfig)
def _drop_pending_of_replaced_profile(sender, instance: QueryNotificationConfig, **kwargs) -> None:
    # Pointing an attachment at another Profile detaches the old Profile and attaches the new one.
    old = sender.objects.filter(pk=instance.pk).values("query_id", "profile_id").first()
    if old is not None and (old["query_id"], old["profile_id"]) != (instance.query_id, instance.profile_id):
        _drop_pending(old["query_id"], old["profile_id"])


@receiver(pre_delete, sender=QueryNotificationConfig)
def _drop_pending_of_detached_profile(sender, instance: QueryNotificationConfig, **kwargs) -> None:
    # pre_delete, not post_delete: deleting a Query clears its Items' `query` before post_delete.
    _drop_pending(instance.query_id, instance.profile_id)


def _drop_pending(query_id: int, profile_id: int) -> None:
    Delivery.objects.filter(item__query_id=query_id, profile_id=profile_id, status=Delivery.Status.PENDING).delete()
