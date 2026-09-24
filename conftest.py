"""
Shared fixtures for the listing_watch and web UI test suites.
"""
from __future__ import annotations

from typing import Callable, Mapping

import pytest

from listing_watch import registry
from listing_watch.notificators import Notificator
from listing_watch.spiders import Spider

InstallPlugins = Callable[..., registry.Registry]


@pytest.fixture(name="installed_plugins")
def installed_plugins_fixture(monkeypatch: pytest.MonkeyPatch) -> InstallPlugins:
    """
    Replaces the installed Plugins with a fixed set of Spiders and Notificators, keyed by name:
    `installed_plugins(spiders={"cars": FakeSpider}, notificators={"pigeon": FakeNotificator})`.
    Anything not passed is not installed.
    """

    def install(
        spiders: Mapping[str, type[Spider]] | None = None,
        notificators: Mapping[str, type[Notificator]] | None = None,
    ) -> registry.Registry:
        fake = registry.Registry(spiders=dict(spiders or {}), notificators=dict(notificators or {}))
        monkeypatch.setattr(registry, "installed", lambda: fake)
        return fake

    return install
