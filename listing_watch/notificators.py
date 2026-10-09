"""
The Notificator base class. Plugins provide the implementations (see the `listing-watch-notificators` Plugin).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from listing_watch.config_field import ConfigField

NotificatorItem = dict[str, str]


class _EmptyForMissing(dict[str, str]):
    """An item's fields for `str.format_map`, where a field the item lacks renders as empty."""

    def __missing__(self, key: str) -> str:
        return ""


class Notificator(ABC):
    """
    Notificator base class. This class is meant to be subclassed for each implementation of different notification
    options.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    # The settings this Notificator needs from the user. The Core renders them as the Notification
    # Profile form and stores the entered values in `configuration`, under each field's key.
    config_fields: Sequence[ConfigField] = ()

    def __init__(self, configuration: dict[str, str | bool]):
        self.configuration = configuration

    @abstractmethod
    def send_text(self, subject: str, message: str) -> None:
        """
        Sends notification.

        :param subject: Subject (title) of notification.
        :param message: Message content.
        """

    @staticmethod
    def _format_item(item: NotificatorItem, item_format: str, include_header: bool) -> str:
        """
        Renders a single item's body via `item_format`, optionally preceded by a "Query: ..."
        header. The header isn't part of `item_format` itself (which no longer contains
        `{query}`) since it's meant to appear once per query, not once per item -- see
        `send_items`.

        :param item: Item to render.
        :param item_format: Format, with which the item's body will be created. A field the item
            doesn't have renders as empty: an Item only has to carry a title and a URL.
        :param include_header: Whether to prepend a "Query: <name>" header line.
        :return: Rendered item, ready to be joined with other items via a blank line.
        """
        body = item_format.format_map(_EmptyForMissing(item)).rstrip()
        if include_header:
            return f"Query: {item['query']}\n\n{body}"
        return body

    def send_items(
        self,
        subject: str,
        items: list[NotificatorItem],
        item_format: str,
    ) -> None:
        """
        Sends items in a form of a dictionary to recipients.

        Items are expected to arrive grouped by `query` (consecutive items sharing the same
        query stay adjacent) -- true for every current spider, which builds its item list one
        query at a time. A "Query: <name>" header is emitted once at the start of each such
        run rather than once per item, since all items in a run share the same query value.

        :param subject: Subject for message.
        :param items: List of dictionaries, containing data as key value pairs, which will be sent to recipients.
        :param item_format: Format, with which each item's message will be created.
        """
        blocks: list[str] = []
        previous_query: str | None = None
        for item in items:
            query = item["query"]
            blocks.append(self._format_item(item, item_format, include_header=query != previous_query))
            previous_query = query

        self.send_text(subject, "\n\n".join(blocks))
