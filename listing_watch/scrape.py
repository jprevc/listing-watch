"""
Sends notifications to configured notificators (e.g. email, Pushover, ntfy) for newly found items.
"""
from __future__ import annotations

import logging
from typing import cast

from listing_watch import notificators
from listing_watch import spiders

logger = logging.getLogger(__name__)


def send_notifications(
    notificator_configs: list[tuple[str, dict[str, str | bool]]],
    spider_name: str,
    new_data: list[spiders.SpiderItem],
) -> None:
    """
    Send new items to all configured notificators (e.g. email, Pushover) for a single spider.

    :param notificator_configs: List of (notificator type name, its config incl. message_body_format)
                                 pairs. A list rather than a dict keyed by type since the same type
                                 can appear more than once (e.g. two differently-configured ntfy
                                 entries).
    :param spider_name: Name of the spider (used in the notification subject/title).
    :param new_data: List of new items to send.
    """
    # send message with each configured notificator; one notificator's failure (e.g. a missing
    # env var or bad credentials) must not prevent the others from delivering their notification
    errors: list[str] = []
    for notificator_type_str, notificator_data in notificator_configs:
        try:
            notificator = notificators.get_notificator_by_name(notificator_type_str)(notificator_data)

            message_body_format = cast(str, notificator_data["message_body_format"])

            notificator.send_items(spider_name + " news", new_data, message_body_format)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Notificator '%s' failed to send notification", notificator_type_str)
            errors.append(f"{notificator_type_str}: {exc}")

    if errors:
        raise RuntimeError("Some notificators failed: " + "; ".join(errors))
