"""
Contains various mock classes which can be used in tests.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from listing_watch import registry
from listing_watch.notificators import Notificator
from listing_watch.spiders import Spider, SpiderItem

# pylint: disable=unused-argument


class FakeCarsSpider(Spider):
    name = "cars"
    item_fields = ("title", "url", "mileage")

    def run(self, max_pages=None, should_stop=None) -> list[SpiderItem]:
        return []


class FakePigeonNotificator(Notificator):
    name = "pigeon"

    def send_text(self, subject: str, message: str) -> None:
        pass


@dataclass
class FakeEntryPoint:
    """
    Stand-in for an installed Plugin's `importlib.metadata.EntryPoint`. Loading it returns
    `target`, or raises it if it's an exception.
    """

    name: str
    group: str
    target: Any
    plugin: str = "some-plugin"

    @property
    def value(self) -> str:
        return f"{self.plugin}.module:{getattr(self.target, '__name__', type(self.target).__name__)}"

    @property
    def dist(self) -> SimpleNamespace:
        return SimpleNamespace(name=self.plugin)

    def load(self) -> Any:
        if isinstance(self.target, Exception):
            raise self.target
        return self.target


def spider_entry_point(name: str, target: Any, plugin: str = "some-plugin") -> FakeEntryPoint:
    return FakeEntryPoint(name, registry.SPIDERS_GROUP, target, plugin)


def notificator_entry_point(name: str, target: Any, plugin: str = "some-plugin") -> FakeEntryPoint:
    return FakeEntryPoint(name, registry.NOTIFICATORS_GROUP, target, plugin)
