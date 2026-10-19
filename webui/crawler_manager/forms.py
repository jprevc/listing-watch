from __future__ import annotations

from typing import Mapping, Sequence

from django import forms
from django.forms import inlineformset_factory

from crawler_manager import schedule_utils
from crawler_manager.models import DEFAULT_MESSAGE_BODY_FORMAT, NotificationProfile, Query, QueryNotificationConfig
from listing_watch import registry
from listing_watch.config_field import ConfigField


def _form_field_name(component_name: str, config_key: str) -> str:
    # Every installed Spider's or Notificator's inputs are on the page at once (the template shows
    # only the chosen one's), and two of them may share a config key, so form names are namespaced.
    return f"{component_name}__{config_key}"


def _django_field(config_field: ConfigField) -> forms.Field:
    """Turns a declared Config Field into a form field. `required` is enforced in the form's clean()."""
    common = {"required": False, "label": config_field.label, "help_text": config_field.help_text}
    if config_field.choices is not None:
        return forms.ChoiceField(
            choices=[("", "---------"), *((choice, choice) for choice in config_field.choices)], **common
        )
    widget = forms.PasswordInput(render_value=True) if config_field.secret else None
    return forms.CharField(widget=widget, **common)


class ConfigFieldsMixin:
    """
    Renders, validates and collects the Config Fields of whichever installed Spider or Notificator
    the form's `component_field` (e.g. `spider_name`) chooses, stored as a dict in `config_attr` on
    the model instance.

    A saved instance that is Unavailable (its component isn't installed) is shown read-only: every
    field is disabled, and its missing component stays selected.
    """

    component_field: str
    config_attr: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_config_fields(self._installed_components())
        if self.instance.pk is not None and self.instance.unavailable_reason:
            self._make_read_only()

    def _installed_components(self) -> Mapping[str, Sequence[ConfigField]]:
        """Each installed component's name -> its declared Config Fields."""
        raise NotImplementedError

    def _make_read_only(self) -> None:
        component_field = self.fields[self.component_field]
        assert isinstance(component_field, forms.ChoiceField)
        stored_component = getattr(self.instance, self.component_field)
        component_field.choices = [(name, name) for name in [*self._config_fields, stored_component]]
        for field in self.fields.values():
            field.disabled = True

    def _add_config_fields(self, components: Mapping[str, Sequence[ConfigField]]) -> None:
        """Adds a form field per Config Field of each component (name -> its declared Config Fields)."""
        stored_config = getattr(self.instance, self.config_attr) if self.instance.pk else {}
        stored_component = getattr(self.instance, self.component_field) if self.instance.pk else None

        # Each component's name -> its (form field name, Config Field) pairs, in render order.
        self._config_fields: dict[str, list[tuple[str, ConfigField]]] = {}
        for component_name, config_fields in components.items():
            fields = self._config_fields[component_name] = []
            for config_field in config_fields:
                form_field_name = _form_field_name(component_name, config_field.key)
                form_field = self.fields[form_field_name] = _django_field(config_field)
                if component_name == stored_component and config_field.key in stored_config:
                    form_field.initial = stored_config[config_field.key]
                else:
                    form_field.initial = config_field.default
                fields.append((form_field_name, config_field))

    @property
    def config_field_groups(self) -> list[tuple[str, list[forms.BoundField]]]:
        """Each component's name with its Config Fields' bound form fields, for the template."""
        return [
            (component_name, [self[form_field_name] for form_field_name, _ in fields])
            for component_name, fields in self._config_fields.items()
        ]

    def _clean_config_fields(self, cleaned: dict) -> None:
        component_name = cleaned.get(self.component_field)
        for form_field_name, config_field in self._config_fields.get(component_name, []):
            if config_field.required and not cleaned.get(form_field_name):
                self.add_error(form_field_name, f"{config_field.label} is required for {component_name}.")

    def _store_config(self) -> None:
        """Sets the chosen component's entered (non-empty) values on the instance, keyed by Config Field key."""
        component_name = self.cleaned_data.get(self.component_field)
        setattr(
            self.instance,
            self.config_attr,
            {
                config_field.key: value
                for form_field_name, config_field in self._config_fields.get(component_name, [])
                if (value := self.cleaned_data.get(form_field_name))
            },
        )


class QueryForm(ConfigFieldsMixin, forms.ModelForm):
    """Create/edit a Query, including the Config Fields its Spider declares."""

    component_field = "spider_name"
    config_attr = "spider_config"

    class Meta:
        model = Query
        fields = [
            "name",
            "spider_name",
            "url",
            "schedule_mode",
            "interval_value",
            "interval_unit",
            "cron_schedule",
            "max_pages",
            "is_active",
        ]
        widgets = {
            "schedule_mode": forms.RadioSelect,
            "interval_value": forms.NumberInput(attrs={"min": 1}),
            "cron_schedule": forms.TextInput(attrs={"placeholder": "*/15 * * * *"}),
            "max_pages": forms.NumberInput(attrs={"placeholder": "unlimited", "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            # New query: pre-fill the simple picker with a sensible default (matches the
            # interval the old raw-cron placeholder used to suggest) rather than leaving it
            # blank and forcing every new user to make a choice just to accept the default.
            self.fields["interval_value"].initial = 15
            self.fields["interval_unit"].initial = schedule_utils.MINUTES

    def _installed_components(self) -> Mapping[str, Sequence[ConfigField]]:
        installed = registry.installed()
        return {name: installed.get_spider(name).config_fields for name in installed.spider_names()}

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("schedule_mode")

        if mode == Query.ScheduleMode.SIMPLE:
            value = cleaned.get("interval_value")
            unit = cleaned.get("interval_unit")
            if not value:
                self.add_error("interval_value", "Enter a number for the schedule interval.")
            if not unit:
                self.add_error("interval_unit", "Choose a unit for the schedule interval.")
            if value and unit:
                low, high = schedule_utils.BOUNDS[unit]
                if not low <= value <= high:
                    self.add_error("interval_value", f"Must be between {low} and {high} for {unit}.")
        elif mode == Query.ScheduleMode.ADVANCED and not cleaned.get("cron_schedule"):
            self.add_error("cron_schedule", "Enter a cron expression, or switch to Simple/Manual.")

        self._clean_config_fields(cleaned)
        return cleaned

    def save(self, commit=True):
        self._store_config()
        return super().save(commit=commit)


class NotificationProfileForm(ConfigFieldsMixin, forms.ModelForm):
    """
    Create/edit a reusable NotificationProfile: its identity fields plus the Config Fields its
    Notificator declares, whose values are stored in the Profile's config under each field's key.
    """

    component_field = "notificator_name"
    config_attr = "config"

    class Meta:
        model = NotificationProfile
        fields = ["name", "notificator_name", "is_default"]

    def _installed_components(self) -> Mapping[str, Sequence[ConfigField]]:
        installed = registry.installed()
        return {name: installed.get_notificator(name).config_fields for name in installed.notificator_names()}

    def clean(self):
        cleaned = super().clean()
        self._clean_config_fields(cleaned)
        return cleaned

    def save(self, commit=True):
        self._store_config()
        return super().save(commit=commit)


class QueryNotificationConfigForm(forms.ModelForm):
    """Attaches one of the user's existing NotificationProfiles to a query, with its message format."""

    class Meta:
        model = QueryNotificationConfig
        fields = ["profile", "message_body_format"]
        widgets = {"message_body_format": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile"].queryset = NotificationProfile.objects.filter(user=user)
        self.fields["profile"].empty_label = "-- select a notification profile --"
        self.fields["message_body_format"].help_text = "str.format() template."
        if self.instance.pk is None:
            self.fields["message_body_format"].initial = DEFAULT_MESSAGE_BODY_FORMAT

    def has_changed(self) -> bool:
        # Deliberately NOT the generic field-by-field has_changed(): that flags a row as
        # "changed" (forcing full validation, incl. a spurious required-field error) the moment
        # ANY field differs from its initial value -- including a hidden extra row whose
        # message_body_format initial value changes in a future code update while an old page is
        # still open. clean() already treats `profile` as the single source of truth for "is this
        # row worth validating" -- reuse that here so an untouched extra row is only ever
        # considered "changed" for the one reason that matters.
        data = self.data if self.is_bound else {}
        value = self.fields["profile"].widget.value_from_datadict(data, self.files, self.add_prefix("profile"))
        return bool(value)

    @property
    def is_blank_extra(self) -> bool:
        """True for a not-yet-saved row with nothing worth showing on page load."""
        if self.instance.pk or self.errors:
            return False
        return not self.has_changed()


def query_notification_formset_class(*, extra: int = 3):
    """
    extra=3 by default: a small pool of blank rows rendered hidden in the template and revealed
    one at a time by the "+ Add notification" button's JS, rather than one empty form always on
    display. `query_create` passes a larger `extra` to also fit the current user's default
    profiles as pre-filled (visible, removable) rows -- see views.py.
    """
    return inlineformset_factory(
        Query,
        QueryNotificationConfig,
        form=QueryNotificationConfigForm,
        extra=extra,
        can_delete=True,
    )


QueryNotificationConfigFormSet = query_notification_formset_class()
