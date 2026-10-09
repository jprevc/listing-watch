"""
The plugin registry: the one place that discovers Spiders and Notificators.

Plugins register their Spiders and Notificators through the `listing_watch.spiders` and
`listing_watch.notificators` entry-point groups. The entry-point name is the Spider's or
Notificator's name, and its value is the class. Until they move to their own Plugin, the Core's
Spiders register the same way, through this package's metadata.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from importlib.metadata import entry_points as installed_entry_points
from typing import Any, Iterable, Mapping, Protocol

from listing_watch.notificators import Notificator
from listing_watch.spiders import GUARANTEED_ITEM_FIELDS, Spider

SPIDERS_GROUP = "listing_watch.spiders"
NOTIFICATORS_GROUP = "listing_watch.notificators"


class PluginNotInstalledError(KeyError):
    """No installed Plugin provides a Spider or Notificator with the requested name."""

    def __init__(self, kind: str, name: str) -> None:
        super().__init__(name)
        self.kind = kind
        self.name = name

    def __str__(self) -> str:
        return f"No installed Plugin provides a {self.kind} named '{self.name}'."


class DuplicatePluginNameError(RuntimeError):
    """Two installed Plugins register the same name in one entry-point group."""


class PluginEntryPoint(Protocol):
    # The subset of `importlib.metadata.EntryPoint` the registry relies on.
    @property
    def name(self) -> str: ...

    @property
    def group(self) -> str: ...

    @property
    def value(self) -> str: ...

    @property
    def dist(self) -> Any: ...

    def load(self) -> Any: ...


def _plugin_label(entry_point: PluginEntryPoint) -> str:
    dist_name = getattr(entry_point.dist, "name", None) or "unknown Plugin"
    return f"{dist_name} ({entry_point.value})"


def _load_group(entry_points: Iterable[PluginEntryPoint], group: str, kind: str) -> dict[str, Any]:
    by_name: dict[str, PluginEntryPoint] = {}
    for entry_point in entry_points:
        if entry_point.group != group:
            continue
        if entry_point.name in by_name:
            raise DuplicatePluginNameError(
                f"Two installed Plugins register a {kind} named '{entry_point.name}': "
                f"{_plugin_label(by_name[entry_point.name])} and {_plugin_label(entry_point)}. "
                "Uninstall one of them."
            )
        by_name[entry_point.name] = entry_point
    return {name: entry_point.load() for name, entry_point in by_name.items()}


@dataclass(frozen=True)
class Registry:
    """The Spiders and Notificators provided by a set of installed Plugins, keyed by name."""

    spiders: Mapping[str, type[Spider]]
    notificators: Mapping[str, type[Notificator]]

    @classmethod
    def from_entry_points(cls, entry_points: Iterable[PluginEntryPoint] | None = None) -> Registry:
        """
        Builds a registry from entry points (by default, every installed package's).

        :raises DuplicatePluginNameError: If two entry points in one group share a name.
        """
        eps = list(installed_entry_points() if entry_points is None else entry_points)
        return cls(
            spiders=_load_group(eps, SPIDERS_GROUP, "Spider"),
            notificators=_load_group(eps, NOTIFICATORS_GROUP, "Notificator"),
        )

    def get_spider(self, name: str) -> type[Spider]:
        """:raises PluginNotInstalledError: If no installed Plugin provides this Spider."""
        try:
            return self.spiders[name]
        except KeyError:
            raise PluginNotInstalledError("Spider", name) from None

    def get_notificator(self, name: str) -> type[Notificator]:
        """:raises PluginNotInstalledError: If no installed Plugin provides this Notificator."""
        try:
            return self.notificators[name]
        except KeyError:
            raise PluginNotInstalledError("Notificator", name) from None

    def spider_names(self) -> list[str]:
        return sorted(self.spiders)

    def notificator_names(self) -> list[str]:
        return sorted(self.notificators)

    def spider_item_fields(self) -> dict[str, list[str]]:
        """
        Maps each Spider's name to the Item fields available in its message formats: the fields
        every Item has, then whatever else the Spider declares.
        """
        return {
            name: list(dict.fromkeys([*GUARANTEED_ITEM_FIELDS, *spider.item_fields]))
            for name, spider in self.spiders.items()
        }


@functools.cache
def installed() -> Registry:
    """
    The registry of every installed Plugin, discovered once and cached for the process.

    :raises DuplicatePluginNameError: If two installed Plugins register the same name.
    """
    return Registry.from_entry_points()
