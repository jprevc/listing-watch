from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from crawler_manager import schedule_utils
from crawler_manager.models import DEFAULT_MESSAGE_BODY_FORMAT, NotificationProfile, Query, QueryNotificationConfig

# Maps each notificator type to its type-specific form fields, as (form_field_name, config_key)
# pairs. Hardcoded against the 3 notificator implementations in listing_watch/notificators.py --
# adding a new Notificator subclass means adding an entry here too.
NOTIFICATOR_TYPE_FIELDS: dict[str, list[tuple[str, str]]] = {
    "email": [
        ("email_user", "email_user"),
        ("email_password", "email_password"),
        ("email_recipients", "recipients"),
    ],
    "pushover": [
        ("app_token", "app_token"),
        ("pushover_recipients", "recipients"),
    ],
    "ntfy": [
        ("topic", "topic"),
        ("server", "server"),
        ("priority", "priority"),
        ("tags", "tags"),
        ("token", "token"),
        ("username", "username"),
        ("password", "password"),
    ],
}

NOTIFICATOR_REQUIRED_FIELDS: dict[str, list[str]] = {
    "email": ["email_user", "email_password", "email_recipients"],
    "pushover": ["app_token", "pushover_recipients"],
    "ntfy": ["topic"],
}


class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = [
            "name", "spider_name", "url",
            "schedule_mode", "interval_value", "interval_unit", "cron_schedule",
            "max_pages", "is_active",
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

        return cleaned


class NotificationProfileForm(forms.ModelForm):
    """Create/edit a reusable NotificationProfile: its identity fields plus its type-specific config."""

    class Meta:
        model = NotificationProfile
        fields = ["name", "notificator_name", "is_default"]

    email_user = forms.CharField(required=False, label="Email address")
    email_password = forms.CharField(
        required=False, label="Email password", widget=forms.PasswordInput(render_value=True)
    )
    email_recipients = forms.CharField(required=False, label="Recipients (comma-separated email addresses)")

    app_token = forms.CharField(
        required=False, label="Pushover app token", widget=forms.PasswordInput(render_value=True)
    )
    pushover_recipients = forms.CharField(required=False, label="Recipients (comma-separated Pushover user keys)")

    topic = forms.CharField(required=False, label="Topic")
    server = forms.CharField(required=False, label="Server URL", initial="https://ntfy.sh")
    priority = forms.CharField(
        required=False,
        label="Priority",
        help_text=(
            "How urgently ntfy delivers/displays the notification: min, low, default, high, or "
            "urgent (or 1-5). Leave blank for default. urgent/5 bypasses silent mode on some devices."
        ),
    )
    tags = forms.CharField(
        required=False,
        label="Tags (comma-separated)",
        help_text=(
            "Comma-separated labels. A tag matching a known emoji short name (e.g. warning, "
            "rotating_light, white_check_mark) is shown as an emoji prefix; other tags are shown as "
            "plain text tags."
        ),
    )
    token = forms.CharField(required=False, label="Auth token", widget=forms.PasswordInput(render_value=True))
    username = forms.CharField(required=False, label="Username")
    password = forms.CharField(required=False, label="Password", widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = self.instance.config if self.instance and self.instance.pk else {}
        notificator_name = self.initial.get("notificator_name") or getattr(self.instance, "notificator_name", "")
        for form_field, config_key in NOTIFICATOR_TYPE_FIELDS.get(notificator_name, []):
            if config_key in config:
                self.fields[form_field].initial = config[config_key]

    def clean(self):
        cleaned = super().clean()
        notificator_name = cleaned.get("notificator_name")
        if not notificator_name:
            return cleaned

        for form_field in NOTIFICATOR_REQUIRED_FIELDS.get(notificator_name, []):
            if not cleaned.get(form_field):
                self.add_error(form_field, "This field is required for the selected notificator.")

        return cleaned

    def save(self, commit=True):
        notificator_name = self.cleaned_data.get("notificator_name")
        config: dict[str, str] = {}

        for form_field, config_key in NOTIFICATOR_TYPE_FIELDS.get(notificator_name, []):
            value = self.cleaned_data.get(form_field)
            if value:
                config[config_key] = value

        self.instance.config = config
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
