"""
Tests for the Plugin contract-test helper, using deliberately broken fake Plugins.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any

import pytest

from listing_watch import contract, registry
from listing_watch.config_field import ConfigField
from listing_watch.spiders import Spider
from tests.mocks import FakeCarsSpider, FakePigeonNotificator, notificator_entry_point, spider_entry_point
from tests.mocks import FakeEntryPoint


def _violations(*entry_points: FakeEntryPoint) -> str:
    with pytest.raises(contract.PluginContractError) as exc_info:
        contract.check_plugin(entry_points)
    return str(exc_info.value)


def test_a_well_formed_plugin_passes() -> None:
    contract.check_plugin(
        [spider_entry_point("cars", FakeCarsSpider), notificator_entry_point("pigeon", FakePigeonNotificator)]
    )


def test_an_entry_point_that_fails_to_load_is_a_violation() -> None:
    message = _violations(spider_entry_point("cars", ModuleNotFoundError("No module named 'fake_plugin'")))

    assert "Spider entry point 'cars'" in message
    assert "some-plugin.module:ModuleNotFoundError" in message
    assert "No module named 'fake_plugin'" in message


@pytest.mark.parametrize(
    "entry_point, expected",
    [
        pytest.param(spider_entry_point("pigeon", FakePigeonNotificator), "doesn't subclass Spider", id="spider"),
        pytest.param(notificator_entry_point("cars", FakeCarsSpider), "doesn't subclass Notificator", id="notificator"),
        pytest.param(spider_entry_point("cars", len), "doesn't subclass Spider", id="not-a-class"),
    ],
)
def test_a_class_that_doesnt_subclass_its_groups_base_is_a_violation(entry_point, expected) -> None:
    message = _violations(entry_point)

    assert f"entry point '{entry_point.name}'" in message
    assert expected in message


def test_a_name_that_doesnt_match_the_entry_point_name_is_a_violation() -> None:
    message = _violations(spider_entry_point("automobiles", FakeCarsSpider))

    assert "Spider entry point 'automobiles'" in message
    assert "name 'cars' doesn't match the entry-point name 'automobiles'" in message


def _with_config_fields(base: type, *config_fields: Any) -> type:
    """A subclass of a well-formed fake Spider or Notificator that declares these Config Fields."""
    return type(f"Configured{base.__name__}", (base,), {"config_fields": config_fields})


@pytest.mark.parametrize(
    "make_ep, base",
    [
        pytest.param(spider_entry_point, FakeCarsSpider, id="spider"),
        pytest.param(notificator_entry_point, FakePigeonNotificator, id="notificator"),
    ],
)
@pytest.mark.parametrize(
    "config_fields, expected",
    [
        pytest.param(
            (ConfigField(key="token", label="Token"), ConfigField(key="token", label="API token")),
            "Config Field key 'token' is declared more than once",
            id="duplicate-key",
        ),
        pytest.param(
            (ConfigField(key="sort", label="Sort", choices=("new", "cheap"), default="old"),),
            "Config Field 'sort' has default 'old', which isn't one of its choices ('new', 'cheap')",
            id="default-not-a-choice",
        ),
        pytest.param(
            (ConfigField(key="sort", label="Sort", choices=()),),
            "Config Field 'sort' has no choices",
            id="empty-choices",
        ),
        pytest.param(
            ({"key": "token", "label": "Token"},),
            "isn't a ConfigField",
            id="not-a-config-field",
        ),
    ],
)
def test_malformed_config_fields_are_violations(make_ep, base, config_fields, expected) -> None:
    message = _violations(make_ep(base.name, _with_config_fields(base, *config_fields)))

    assert f"entry point '{base.name}'" in message
    assert expected in message


def test_well_formed_config_fields_pass() -> None:
    spider = _with_config_fields(
        FakeCarsSpider,
        ConfigField(key="token", label="Token", required=True, secret=True),
        ConfigField(key="sort", label="Sort", choices=("new", "cheap"), default="cheap"),
        ConfigField(key="region", label="Region", default="anywhere"),
    )

    contract.check_plugin([spider_entry_point("cars", spider)])


@pytest.mark.parametrize(
    "item_fields, missing",
    [
        pytest.param(("url", "price"), "'title'", id="no-title"),
        pytest.param(("title", "price"), "'url'", id="no-url"),
        pytest.param((), "'title', 'url'", id="none-declared"),
    ],
)
def test_a_spider_whose_item_fields_lack_title_or_url_is_a_violation(item_fields, missing) -> None:
    spider = type("UndeclaredSpider", (FakeCarsSpider,), {"item_fields": item_fields})

    message = _violations(spider_entry_point("cars", spider))

    assert "Spider entry point 'cars'" in message
    assert f"Item fields must include {missing}" in message


def test_a_plugin_with_no_spider_or_notificator_entry_points_is_a_violation() -> None:
    # E.g. a typo in the entry-point group name, which would otherwise pass silently.
    message = _violations(FakeEntryPoint("cars", "listing_watch.spider", FakeCarsSpider))

    assert "provides no Spiders or Notificators" in message
    assert registry.SPIDERS_GROUP in message


def test_every_violation_is_reported_at_once() -> None:
    message = _violations(
        spider_entry_point("automobiles", FakeCarsSpider), notificator_entry_point("pigeon", ImportError("boom"))
    )

    assert "Spider entry point 'automobiles'" in message
    assert "Notificator entry point 'pigeon'" in message


def test_the_helper_is_importable_without_django() -> None:
    # Run in a fresh interpreter: this test process has Django loaded by pytest-django.
    code = "import sys, listing_watch.contract; assert 'django' not in sys.modules, 'django was imported'"

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr


def test_an_abstract_class_is_a_violation_naming_what_it_doesnt_implement() -> None:
    class _UnfinishedSpider(Spider):  # declares neither `name` nor `run`
        item_fields = ("title", "url")

    message = _violations(spider_entry_point("cars", _UnfinishedSpider))

    assert "Spider entry point 'cars'" in message
    assert "is abstract: it doesn't implement 'name', 'run'" in message
    assert "property object" not in message
