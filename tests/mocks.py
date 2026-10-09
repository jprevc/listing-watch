"""
Contains various mock classes which can be used in tests.
"""

import pathlib
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import requests

from listing_watch import registry
from listing_watch.notificators import Notificator
from listing_watch.spiders import Spider, SpiderItem

# pylint: disable=unused-argument


def mock_get_raw_html(mock_html: str) -> str:
    mock_html_path = pathlib.Path(__file__).parent / "res" / mock_html

    with open(mock_html_path, encoding="utf8") as file:
        html_content = file.read()

    return html_content


class MockRequestObject:
    def __init__(self, mock_html, error_status: int = 404):
        self.mock_html = mock_html
        self.request_counter = 0
        self.error_status = error_status

    @property
    def text(self) -> str:
        self.request_counter += 1
        return mock_get_raw_html(self.mock_html)

    @property
    def status_code(self) -> int:
        return 200 if self.request_counter < 1 else self.error_status

    def raise_for_status(self) -> None:
        """Mimic requests.Response: raise on 4xx/5xx (mock errors out after the first call)."""
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.raise_for_status()


def mock_requests_get(mock_html: str, error_status: int = 404) -> Callable[[str, str, str], MockRequestObject]:
    mock_request_obj = MockRequestObject(mock_html, error_status=error_status)

    def mock_request_func(url: str, headers: str, timeout: str) -> MockRequestObject:
        return mock_request_obj

    return mock_request_func


class FakePlaywrightResponse:
    """Minimal stand-in for playwright.sync_api.Response: just exposes .status."""

    def __init__(self, status: int):
        self.status = status


class FakePlaywrightPage:
    """Minimal stand-in for playwright.sync_api.Page.

    Takes a fixed sequence of (html, status) pairs, one per expected .goto() call, and replays
    them in order -- so exampleSpider's pagination/parsing logic can be tested without a real
    browser.
    """

    def __init__(self, responses: list[tuple[str, int]]):
        self._responses = list(responses)
        self._current_html = ""

    def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None) -> FakePlaywrightResponse:
        self._current_html, status = self._responses.pop(0)
        return FakePlaywrightResponse(status)

    def content(self) -> str:
        return self._current_html


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
