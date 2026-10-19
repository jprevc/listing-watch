"""
Tests for the demo Plugin: the Demo Market's posting schedule, and the Spider crawling a live
Demo Market served on a free local port.
"""
from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from typing import Iterator

import pytest

from listing_watch.contract import check_plugin
from listing_watch_demo.market import PAGE_SIZE, Market, make_handler
from listing_watch_demo.spider import DemoMarketSpider


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(name="clock")
def clock_fixture() -> FakeClock:
    return FakeClock()


@pytest.fixture(name="market")
def market_fixture(clock: FakeClock) -> Market:
    return Market(interval=60, initial=7, clock=clock)


@pytest.fixture(name="market_url")
def market_url_fixture(market: Market) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(market, ""))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


def test_the_plugin_satisfies_the_plugin_interface() -> None:
    check_plugin("listing-watch-demo")


def test_a_new_listing_is_posted_every_interval(market: Market, clock: FakeClock) -> None:
    assert market.posted_count() == 7
    clock.now += 59
    assert market.posted_count() == 7
    clock.now += 1
    assert market.posted_count() == 8
    assert market.listing(9) is None


def test_pages_list_the_newest_listings_first(market: Market) -> None:
    first, has_next = market.page(1)
    assert [listing.id for listing in first] == [7, 6, 5, 4, 3]
    assert has_next
    second, has_next = market.page(2)
    assert [listing.id for listing in second] == [2, 1]
    assert not has_next


def test_the_spider_follows_every_page(market_url: str) -> None:
    items = DemoMarketSpider("Bikes", market_url).run()

    assert len(items) == 7
    assert items[0] == {
        "title": items[0]["title"],
        "url": f"{market_url}listing/7",
        "price": items[0]["price"],
        "location": items[0]["location"],
    }
    assert all(item["title"] and item["price"].startswith("€") for item in items)


def test_the_spider_finds_a_newly_posted_listing(market_url: str, clock: FakeClock) -> None:
    spider = DemoMarketSpider("Bikes", market_url)
    before = {item["url"] for item in spider.run()}
    clock.now += 60

    after = {item["url"] for item in spider.run()}

    assert after - before == {f"{market_url}listing/8"}


def test_the_spider_stops_after_max_pages(market_url: str) -> None:
    assert len(DemoMarketSpider("Bikes", market_url).run(max_pages=1)) == PAGE_SIZE


def test_the_spider_stops_when_asked_between_pages(market_url: str) -> None:
    assert len(DemoMarketSpider("Bikes", market_url).run(should_stop=lambda: True)) == PAGE_SIZE


def test_the_spider_skips_listings_above_the_max_price(market_url: str) -> None:
    items = DemoMarketSpider("Cheap", market_url, config={"max_price": "100"}).run()

    assert items
    assert all(int(item["price"].removeprefix("€")) <= 100 for item in items)
