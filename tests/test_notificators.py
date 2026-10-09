"""
Contains tests for the Notificator base class's message rendering, which every Plugin's Notificator inherits.
"""
from __future__ import annotations

import pytest

from listing_watch.notificators import Notificator


class _RecordingNotificator(Notificator):
    name = "pigeon"

    def __init__(self, configuration: dict[str, str | bool]):
        super().__init__(configuration)
        self.sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        self.sent.append((subject, message))


@pytest.fixture(name="notificator")
def notificator_fixture() -> _RecordingNotificator:
    return _RecordingNotificator({})


def test_send_items_shows_query_header_once_per_group(notificator: _RecordingNotificator) -> None:
    """
    'send_items' should print "Query: ..." once at the start of each run of same-query items, not
    once per item, and separate items with a blank line.
    """
    items = [
        {"query": "q1", "title": "a"},
        {"query": "q1", "title": "b"},
        {"query": "q2", "title": "c"},
    ]
    notificator.send_items("subject", items, "{title}")

    assert notificator.sent == [("subject", "Query: q1\n\na\n\nb\n\nQuery: q2\n\nc")]


def test_send_items_renders_a_field_the_item_lacks_as_empty(notificator: _RecordingNotificator) -> None:
    """
    An Item only has to carry a title and a URL, so a message format naming another field (e.g.
    the default format's `{price}`) must still render when the item doesn't have it.
    """
    items = [{"query": "q1", "title": "a", "url": "https://example.com/a"}]
    notificator.send_items("subject", items, "Title: {title}\nURL: {url}\nPrice: {price}")

    assert notificator.sent == [("subject", "Query: q1\n\nTitle: a\nURL: https://example.com/a\nPrice:")]
