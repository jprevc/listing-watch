"""
Django model field choices and web UI hints built from the installed Plugins.

Kept separate from models.py/services.py to avoid a circular import: models.py needs these
choices for its field definitions, and services.py needs the models themselves. Migrations also
reference the choice callables by this module path, so they must stay here.
"""

from __future__ import annotations

from listing_watch import registry


def available_spider_choices() -> list[tuple[str, str]]:
    return [(name, name) for name in registry.installed().spider_names()]


def spider_item_fields() -> dict[str, list[str]]:
    """Maps each Spider's name to the Item fields it declares, for use in the web UI."""
    return registry.installed().spider_item_fields()


def available_notificator_choices() -> list[tuple[str, str]]:
    return [(name, name) for name in registry.installed().notificator_names()]


def spider_unavailable_reason(spider_name: str) -> str:
    """Why a Query using this Spider is Unavailable (no installed Plugin provides it), or "" if it's installed."""
    try:
        registry.installed().get_spider(spider_name)
    except registry.PluginNotInstalledError as exc:
        return str(exc)
    return ""
