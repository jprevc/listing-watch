"""
Tests for the plugin registry, using fake entry-point objects in place of installed Plugins.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from listing_watch import registry
from listing_watch.notificators import Notificator
from listing_watch.spiders import Spider, SpiderItem


class _CarsSpider(Spider):
    name = "cars"
    item_fields = ("title", "url", "mileage")

    def run(self, max_pages=None, should_stop=None) -> list[SpiderItem]:
        return []


class _BikesSpider(Spider):
    name = "bikes"

    def run(self, max_pages=None, should_stop=None) -> list[SpiderItem]:
        return []


class _PigeonNotificator(Notificator):
    name = "pigeon"

    def send_text(self, subject: str, message: str) -> None:
        pass


@dataclass
class _FakeEntryPoint:
    name: str
    group: str
    target: type
    plugin: str

    @property
    def value(self) -> str:
        return f"{self.plugin}.module:{self.target.__name__}"

    @property
    def dist(self) -> SimpleNamespace:
        return SimpleNamespace(name=self.plugin)

    def load(self) -> type:
        return self.target


def _spider_ep(name: str, target: type, plugin: str = "some-plugin") -> _FakeEntryPoint:
    return _FakeEntryPoint(name, registry.SPIDERS_GROUP, target, plugin)


def _notificator_ep(name: str, target: type, plugin: str = "some-plugin") -> _FakeEntryPoint:
    return _FakeEntryPoint(name, registry.NOTIFICATORS_GROUP, target, plugin)


def test_one_plugin_can_provide_several_spiders_and_notificators() -> None:
    plugins = registry.Registry.from_entry_points(
        [
            _spider_ep("cars", _CarsSpider, plugin="vehicles"),
            _spider_ep("bikes", _BikesSpider, plugin="vehicles"),
            _notificator_ep("pigeon", _PigeonNotificator, plugin="vehicles"),
        ]
    )

    assert plugins.spider_names() == ["bikes", "cars"]
    assert plugins.get_spider("cars") is _CarsSpider
    assert plugins.get_spider("bikes") is _BikesSpider
    assert plugins.notificator_names() == ["pigeon"]
    assert plugins.get_notificator("pigeon") is _PigeonNotificator


def test_spider_item_fields_are_keyed_by_spider_name() -> None:
    plugins = registry.Registry.from_entry_points(
        [_spider_ep("cars", _CarsSpider), _spider_ep("bikes", _BikesSpider)]
    )

    assert plugins.spider_item_fields() == {"cars": ["title", "url", "mileage"], "bikes": []}


def test_entry_points_from_other_groups_are_ignored() -> None:
    plugins = registry.Registry.from_entry_points(
        [_spider_ep("cars", _CarsSpider), _FakeEntryPoint("cars", "some.other.group", _BikesSpider, "other")]
    )

    assert plugins.get_spider("cars") is _CarsSpider


@pytest.mark.parametrize(
    "make_ep",
    [
        pytest.param(_spider_ep, id="spiders"),
        pytest.param(_notificator_ep, id="notificators"),
    ],
)
def test_duplicate_name_is_an_error_naming_both_plugins(make_ep) -> None:
    with pytest.raises(registry.DuplicatePluginNameError) as exc_info:
        registry.Registry.from_entry_points(
            [make_ep("dupe", _CarsSpider, plugin="plugin-one"), make_ep("dupe", _BikesSpider, plugin="plugin-two")]
        )

    message = str(exc_info.value)
    assert "dupe" in message
    assert "plugin-one" in message
    assert "plugin-two" in message


def test_same_name_in_different_groups_is_not_a_duplicate() -> None:
    plugins = registry.Registry.from_entry_points(
        [_spider_ep("shared", _CarsSpider), _notificator_ep("shared", _PigeonNotificator)]
    )

    assert plugins.get_spider("shared") is _CarsSpider
    assert plugins.get_notificator("shared") is _PigeonNotificator


def test_looking_up_a_missing_spider_raises_not_installed() -> None:
    plugins = registry.Registry.from_entry_points([_spider_ep("cars", _CarsSpider)])

    with pytest.raises(registry.PluginNotInstalledError) as exc_info:
        plugins.get_spider("boats")

    assert "boats" in str(exc_info.value)


def test_looking_up_a_missing_notificator_raises_not_installed() -> None:
    plugins = registry.Registry.from_entry_points([])

    with pytest.raises(registry.PluginNotInstalledError) as exc_info:
        plugins.get_notificator("pigeon")

    assert "pigeon" in str(exc_info.value)


def test_installed_package_registers_its_own_spiders_and_notificators() -> None:
    # The Core's own Spiders and Notificators are found through the package's entry points,
    # exactly like an external Plugin's would be.
    plugins = registry.Registry.from_entry_points()

    assert plugins.spider_names() == ["example", "example"]
    assert plugins.notificator_names() == ["email", "ntfy", "pushover"]
