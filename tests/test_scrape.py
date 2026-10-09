"""
Contains tests for sending notifications about newly found Items.
"""
from __future__ import annotations

from listing_watch import scrape
from listing_watch.notificators import Notificator


class _RecordingNotificator(Notificator):
    name = "pigeon"
    sent: list[tuple[str, str]] = []

    def send_text(self, subject: str, message: str) -> None:
        self.sent.append((subject, message))


def test_send_notifications_supplies_the_query_name_for_items_without_one(installed_plugins) -> None:
    sent = _RecordingNotificator.sent = []
    installed_plugins(notificators={"pigeon": _RecordingNotificator})
    items = [{"title": "a", "url": "https://example.com/a"}, {"title": "b", "url": "https://example.com/b"}]

    scrape.send_notifications([("Carrier", "pigeon", {"message_body_format": "{title}"})], "cars", items)

    assert sent == [("cars news", "Query: cars\n\na\n\nb")]


def test_send_notifications_names_items_by_the_query_even_if_the_spider_set_its_own(installed_plugins) -> None:
    sent = _RecordingNotificator.sent = []
    installed_plugins(notificators={"pigeon": _RecordingNotificator})
    items = [{"query": "something else", "title": "a", "url": "https://example.com/a"}]

    scrape.send_notifications([("Carrier", "pigeon", {"message_body_format": "{title} ({query})"})], "cars", items)

    assert sent == [("cars news", "Query: cars\n\na (cars)")]
