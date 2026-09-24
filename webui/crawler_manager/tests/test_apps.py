import pytest
from django.apps import apps

from listing_watch import registry


def test_duplicate_plugin_names_stop_the_core_from_starting(monkeypatch) -> None:
    def _duplicate():
        raise registry.DuplicatePluginNameError("Two installed Plugins register a Spider named 'cars'")

    monkeypatch.setattr(registry, "installed", _duplicate)

    with pytest.raises(registry.DuplicatePluginNameError):
        apps.get_app_config("crawler_manager").ready()
