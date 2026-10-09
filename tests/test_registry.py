"""
Tests for the plugin registry, using fake entry-point objects in place of installed Plugins.
"""
from __future__ import annotations

import importlib.metadata

import pytest

from listing_watch import registry
from listing_watch.spiders import Spider, SpiderItem
from tests.mocks import (
    FakeCarsSpider,
    FakeEntryPoint,
    FakePigeonNotificator,
    notificator_entry_point,
    spider_entry_point,
)


class _BikesSpider(Spider):
    name = "bikes"

    def run(self, max_pages=None, should_stop=None) -> list[SpiderItem]:
        return []


def test_one_plugin_can_provide_several_spiders_and_notificators() -> None:
    plugins = registry.Registry.from_entry_points(
        [
            spider_entry_point("cars", FakeCarsSpider, plugin="vehicles"),
            spider_entry_point("bikes", _BikesSpider, plugin="vehicles"),
            notificator_entry_point("pigeon", FakePigeonNotificator, plugin="vehicles"),
        ]
    )

    assert plugins.spider_names() == ["bikes", "cars"]
    assert plugins.get_spider("cars") is FakeCarsSpider
    assert plugins.get_spider("bikes") is _BikesSpider
    assert plugins.notificator_names() == ["pigeon"]
    assert plugins.get_notificator("pigeon") is FakePigeonNotificator


def test_spider_item_fields_are_keyed_by_spider_name_and_always_include_the_guaranteed_fields() -> None:
    """
    Every Item has `query` (supplied by the core), `title` and `url`, so they're listed even for a
    Spider that doesn't declare them, ahead of whatever else it declares.
    """
    plugins = registry.Registry.from_entry_points(
        [spider_entry_point("cars", FakeCarsSpider), spider_entry_point("bikes", _BikesSpider)]
    )

    assert plugins.spider_item_fields() == {
        "cars": ["query", "title", "url", "mileage"],
        "bikes": ["query", "title", "url"],
    }


def test_entry_points_from_other_groups_are_ignored() -> None:
    plugins = registry.Registry.from_entry_points(
        [spider_entry_point("cars", FakeCarsSpider), FakeEntryPoint("cars", "some.other.group", _BikesSpider, "other")]
    )

    assert plugins.get_spider("cars") is FakeCarsSpider


@pytest.mark.parametrize(
    "make_ep",
    [
        pytest.param(spider_entry_point, id="spiders"),
        pytest.param(notificator_entry_point, id="notificators"),
    ],
)
def test_duplicate_name_is_an_error_naming_both_plugins(make_ep) -> None:
    with pytest.raises(registry.DuplicatePluginNameError) as exc_info:
        registry.Registry.from_entry_points(
            [make_ep("dupe", FakeCarsSpider, plugin="plugin-one"), make_ep("dupe", _BikesSpider, plugin="plugin-two")]
        )

    message = str(exc_info.value)
    assert "dupe" in message
    assert "plugin-one" in message
    assert "plugin-two" in message


def test_same_name_in_different_groups_is_not_a_duplicate() -> None:
    plugins = registry.Registry.from_entry_points(
        [spider_entry_point("shared", FakeCarsSpider), notificator_entry_point("shared", FakePigeonNotificator)]
    )

    assert plugins.get_spider("shared") is FakeCarsSpider
    assert plugins.get_notificator("shared") is FakePigeonNotificator


def test_looking_up_a_missing_spider_raises_not_installed() -> None:
    plugins = registry.Registry.from_entry_points([spider_entry_point("cars", FakeCarsSpider)])

    with pytest.raises(registry.PluginNotInstalledError) as exc_info:
        plugins.get_spider("boats")

    assert "boats" in str(exc_info.value)


def test_looking_up_a_missing_notificator_raises_not_installed() -> None:
    plugins = registry.Registry.from_entry_points([])

    with pytest.raises(registry.PluginNotInstalledError) as exc_info:
        plugins.get_notificator("pigeon")

    assert "pigeon" in str(exc_info.value)


def test_installed_package_registers_its_own_spiders_but_no_notificators() -> None:
    # The Core's own Spiders are found through the package's entry points, exactly like an external
    # Plugin's would be. Notificators come only from Plugins (e.g. `listing-watch-notificators`).
    plugins = registry.Registry.from_entry_points(
        ep for ep in importlib.metadata.entry_points() if ep.dist and ep.dist.name == "listing-watch"
    )

    assert plugins.spider_names() == ["example", "example"]
    assert plugins.notificator_names() == []
