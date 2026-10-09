"""
The Plugin contract-test helper: checks that a Plugin satisfies the Core's Plugin interface.

A Plugin calls `check_plugin` from its own test suite, passing its distribution name, and the test
fails with a message listing every violation. Deliberately framework-free, so Plugins can use it
without pulling in Django.
"""
from __future__ import annotations

import inspect
from importlib.metadata import Distribution, distribution
from typing import Any, Iterable, cast

from listing_watch.config_field import ConfigField
from listing_watch.notificators import Notificator
from listing_watch.registry import NOTIFICATORS_GROUP, SPIDERS_GROUP, PluginEntryPoint
from listing_watch.spiders import REQUIRED_ITEM_FIELDS, Spider

PluginClass = type[Spider] | type[Notificator]

_BASES: dict[str, PluginClass] = {SPIDERS_GROUP: Spider, NOTIFICATORS_GROUP: Notificator}


class PluginContractError(AssertionError):
    """A Plugin violates the Core's Plugin interface. The message lists every violation."""


def _entry_points(plugin: str | Distribution | Iterable[PluginEntryPoint]) -> list[PluginEntryPoint]:
    if isinstance(plugin, str):
        plugin = distribution(plugin)
    if isinstance(plugin, Distribution):
        return list(plugin.entry_points)
    return list(plugin)


def _class_violations(entry_point_name: str, cls: PluginClass) -> list[str]:
    violations = []
    if inspect.isabstract(cls):
        unimplemented = ", ".join(repr(member) for member in sorted(cls.__abstractmethods__))
        violations.append(f"is abstract: it doesn't implement {unimplemented}")
    # An undeclared `name` is still the base class's abstract property, reported above.
    if isinstance(cls.name, str) and cls.name != entry_point_name:
        violations.append(f"name {cls.name!r} doesn't match the entry-point name '{entry_point_name}'")
    violations.extend(_config_field_violations(cls.config_fields))
    if issubclass(cls, Spider):
        missing = [field for field in REQUIRED_ITEM_FIELDS if field not in cls.item_fields]
        if missing:
            violations.append(f"Item fields must include {', '.join(map(repr, missing))}")
    return violations


def _config_field_violations(config_fields: Iterable[Any]) -> list[str]:
    violations = []
    seen_keys: set[str] = set()
    for config_field in config_fields:
        if not isinstance(config_field, ConfigField):
            violations.append(f"{config_field!r} isn't a ConfigField")
            continue
        if config_field.key in seen_keys:
            violations.append(f"Config Field key '{config_field.key}' is declared more than once")
        seen_keys.add(config_field.key)
        if config_field.choices is None:
            continue
        if not config_field.choices:
            violations.append(f"Config Field '{config_field.key}' has no choices")
        elif config_field.default is not None and config_field.default not in config_field.choices:
            violations.append(
                f"Config Field '{config_field.key}' has default '{config_field.default}', "
                f"which isn't one of its choices {config_field.choices!r}"
            )
    return violations


def check_plugin(plugin: str | Distribution | Iterable[PluginEntryPoint]) -> None:
    """
    Checks a Plugin's Spiders and Notificators against the Core's Plugin interface.

    :param plugin: The Plugin's distribution name (e.g. `"listing-watch-notificators"`), its
        distribution, or its entry points.
    :raises PluginContractError: If the Plugin violates the interface, listing every violation.
    """
    violations: list[str] = []
    plugin_entry_points = [ep for ep in _entry_points(plugin) if ep.group in _BASES]
    if not plugin_entry_points:
        violations.append(
            f"provides no Spiders or Notificators (no '{SPIDERS_GROUP}' or '{NOTIFICATORS_GROUP}' entry points)"
        )
    for entry_point in plugin_entry_points:
        base = _BASES[entry_point.group]
        label = f"{base.__name__} entry point '{entry_point.name}' ({entry_point.value})"
        try:
            cls = entry_point.load()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            violations.append(f"{label} failed to load: {exc!r}")
            continue
        if not (isinstance(cls, type) and issubclass(cls, base)):
            violations.append(f"{label}: {cls!r} doesn't subclass {base.__name__}")
            continue
        # The issubclass check above guarantees this; mypy can't narrow against a non-literal base.
        plugin_class = cast(PluginClass, cls)
        violations.extend(f"{label}: {violation}" for violation in _class_violations(entry_point.name, plugin_class))

    if violations:
        raise PluginContractError(
            "The Plugin violates the Core's Plugin interface:\n"
            + "\n".join(f"- {violation}" for violation in violations)
        )
