"""
Sends notifications to configured notificators (e.g. email, Pushover, ntfy) for newly found items.
"""
from __future__ import annotations

import logging
from typing import cast

from listing_watch import registry
from listing_watch import spiders

logger = logging.getLogger(__name__)


def send_notifications(
    notificator_configs: list[tuple[str, str, dict[str, str | bool]]],
    query_name: str,
    new_data: list[spiders.SpiderItem],
) -> None:
    """
    Send new items to all configured notificators (e.g. email, Pushover) for a single Query.

    :param notificator_configs: List of (label, notificator type name, its config incl.
                                 message_body_format) triples. A list rather than a dict keyed by
                                 type since the same type can appear more than once (e.g. two
                                 differently-configured ntfy entries); the label tells them apart
                                 in failure messages.
    :param query_name: Name of the Query the items were found by (used in the notification
                       subject/title, and as each item's `query`).
    :param new_data: List of new items to send.
    :raises RuntimeError: If any notificator failed, naming each failure; the others still send.
    """
    # The core, not the Spider, names the Query: an Item only has to carry a title and a URL, but
    # Notificators group items under a "Query: ..." header read from each item's `query`.
    items = [{**item, "query": query_name} for item in new_data]

    # send message with each configured notificator; one notificator's failure (e.g. a missing
    # env var or bad credentials) must not prevent the others from delivering their notification
    errors: list[str] = []
    for label, notificator_type_str, notificator_data in notificator_configs:
        try:
            notificator = registry.installed().get_notificator(notificator_type_str)(notificator_data)

            message_body_format = cast(str, notificator_data["message_body_format"])

            notificator.send_items(query_name + " news", items, message_body_format)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Notificator '%s' failed to send notification for %s", notificator_type_str, label)
            errors.append(f"{label}: {exc}")

    if errors:
        raise RuntimeError("Some notificators failed: " + "; ".join(errors))
