"""
The demo Spider: crawls the Demo Market (see `market`) and returns its listings as Items.

Standard library only, so it doubles as a minimal example of a Spider Plugin: subclass `Spider`, set
`name`, declare `item_fields` and `config_fields`, and implement `run()`.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urljoin
from urllib.request import urlopen

from listing_watch.config_field import ConfigField
from listing_watch.spiders import Spider, SpiderItem

REQUEST_TIMEOUT_SECONDS = 10


class _ListingPageParser(HTMLParser):
    """Collects the listings on one Demo Market page, and the link to the next page, if any."""

    def __init__(self) -> None:
        super().__init__()
        self.items: list[SpiderItem] = []
        self.next_href: str | None = None
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "article" and "listing" in classes:
            self.items.append({})
        elif tag == "a" and attributes.get("rel") == "next":
            self.next_href = attributes.get("href")
        elif self.items and (field := next((c for c in classes if c in ("title", "location", "price")), None)):
            self._field = field
            if field == "title":
                self.items[-1]["url"] = attributes.get("href") or ""

    def handle_data(self, data: str) -> None:
        if self._field:
            self.items[-1][self._field] = self.items[-1].get(self._field, "") + data.strip()

    def handle_endtag(self, tag: str) -> None:
        self._field = None


def _price_value(price: str) -> int | None:
    digits = re.sub(r"\D", "", price)
    return int(digits) if digits else None


class DemoMarketSpider(Spider):
    name = "demo-market"
    item_fields = ("title", "url", "price", "location")
    config_fields = (
        ConfigField(
            key="max_price",
            label="Max price (€)",
            help_text="Only notify about listings at or below this price. Leave blank for any price.",
        ),
    )

    def run(
        self, max_pages: int | None = None, should_stop: Callable[[], bool] | None = None
    ) -> list[SpiderItem]:
        max_price = _price_value(self.config.get("max_price", ""))
        items: list[SpiderItem] = []
        page_url: str | None = self.url
        pages = 0
        while page_url and (max_pages is None or pages < max_pages):
            if pages and should_stop and should_stop():
                break
            with urlopen(page_url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                parser = _ListingPageParser()
                parser.feed(response.read().decode("utf-8"))
            pages += 1
            for item in parser.items:
                item["url"] = urljoin(page_url, item["url"])
                price = _price_value(item.get("price", ""))
                if max_price is None or (price is not None and price <= max_price):
                    items.append(item)
            page_url = urljoin(page_url, parser.next_href) if parser.next_href else None
        return items
