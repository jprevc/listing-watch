import pytest

from crawler_manager.forms import NotificationProfileForm, QueryForm
from crawler_manager.models import NotificationProfile, Query
from listing_watch.config_field import ConfigField
from listing_watch.notificators import Notificator
from listing_watch.spiders import Spider

pytestmark = pytest.mark.django_db


class _BikesSpider(Spider):
    name = "bikes"
    config_fields = (ConfigField(key="frame", label="Frame size"),)

    def run(self, max_pages=None, should_stop=None):
        return []


class _PigeonNotificator(Notificator):
    name = "pigeon"
    config_fields = (ConfigField(key="roost", label="Roost address"),)

    def send_text(self, subject: str, message: str) -> None:
        pass


def test_query_form_of_an_unavailable_query_disables_every_field_and_keeps_its_spider_selected(
    installed_plugins,
) -> None:
    installed_plugins(spiders={"bikes": _BikesSpider})
    query = Query.objects.create(name="old_cars", spider_name="cars", url="https://example.com")

    form = QueryForm(instance=query)

    assert all(field.disabled for field in form.fields.values())
    assert ("cars", "cars") in form.fields["spider_name"].choices
    assert form["spider_name"].value() == "cars"


def test_query_form_of_an_available_query_stays_editable(installed_plugins) -> None:
    installed_plugins(spiders={"bikes": _BikesSpider})
    query = Query.objects.create(name="new_bikes", spider_name="bikes", url="https://example.com")

    form = QueryForm(instance=query)

    assert not any(field.disabled for field in form.fields.values())


def test_profile_form_of_an_unavailable_profile_disables_every_field_and_keeps_its_notificator_selected(
    django_user_model, installed_plugins
) -> None:
    installed_plugins(notificators={"pigeon": _PigeonNotificator})
    user = django_user_model.objects.create(username="owner")
    profile = NotificationProfile.objects.create(
        user=user, name="Old", notificator_name="smoke", config={"hill": "north"}
    )

    form = NotificationProfileForm(instance=profile)

    assert all(field.disabled for field in form.fields.values())
    assert ("smoke", "smoke") in form.fields["notificator_name"].choices
    assert form["notificator_name"].value() == "smoke"


def test_profile_form_of_an_available_profile_stays_editable(django_user_model, installed_plugins) -> None:
    installed_plugins(notificators={"pigeon": _PigeonNotificator})
    user = django_user_model.objects.create(username="owner")
    profile = NotificationProfile.objects.create(user=user, name="Carrier", notificator_name="pigeon", config={})

    form = NotificationProfileForm(instance=profile)

    assert not any(field.disabled for field in form.fields.values())
