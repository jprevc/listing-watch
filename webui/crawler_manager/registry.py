"""
Introspects the listing_watch spider/notificator registries to build Django model field choices.

Kept separate from models.py/services.py to avoid a circular import: models.py needs these
choices for its field definitions, and services.py needs the models themselves.
"""

from __future__ import annotations

import inspect
from typing import cast

from listing_watch import notificators, spiders


def available_spider_choices() -> list[tuple[str, str]]:
    return sorted(
        (cast(str, obj.name), cast(str, obj.name))
        for _, obj in inspect.getmembers(spiders)
        if inspect.isclass(obj) and issubclass(obj, spiders.Spider) and obj is not spiders.Spider
    )


def spider_item_fields() -> dict[str, list[str]]:
    """Maps each spider's `name` to the keys its `run()` items contain, for use in the web UI."""
    return {
        cast(str, obj.name): list(obj.item_fields)
        for _, obj in inspect.getmembers(spiders)
        if inspect.isclass(obj) and issubclass(obj, spiders.Spider) and obj is not spiders.Spider
    }


def available_notificator_choices() -> list[tuple[str, str]]:
    return sorted(
        (cast(str, obj.name), cast(str, obj.name))
        for _, obj in inspect.getmembers(notificators)
        if inspect.isclass(obj) and issubclass(obj, notificators.Notificator) and obj is not notificators.Notificator
    )
