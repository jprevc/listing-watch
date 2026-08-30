from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from crawler_manager.models import Query, QueryNotificationConfig

# Maps each notificator type to its type-specific form fields, as (form_field_name, config_key)
# pairs. Hardcoded against the 3 notificator implementations in news_crawlers/notificators.py --
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
        fields = ["name", "spider_name", "url", "cron_schedule", "is_active"]
        widgets = {
            "cron_schedule": forms.TextInput(attrs={"placeholder": "*/15 * * * * (leave blank for manual only)"}),
        }


class QueryNotificationConfigForm(forms.ModelForm):
    class Meta:
        model = QueryNotificationConfig
        fields = ["notificator_name", "enabled"]

    DEFAULT_MESSAGE_BODY_FORMAT = "Query: {query}\nTitle: {title}\nURL: {url}\nPrice: {price}"

    message_body_format = forms.CharField(
        required=False,
        initial=DEFAULT_MESSAGE_BODY_FORMAT,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="str.format() template; available keys depend on the spider's item fields.",
    )
    send_separately = forms.BooleanField(
        required=False, help_text="Send one notification per item instead of batching them together."
    )

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
    priority = forms.CharField(required=False, label="Priority")
    tags = forms.CharField(required=False, label="Tags (comma-separated)")
    token = forms.CharField(required=False, label="Auth token", widget=forms.PasswordInput(render_value=True))
    username = forms.CharField(required=False, label="Username")
    password = forms.CharField(required=False, label="Password", widget=forms.PasswordInput(render_value=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = self.instance.config if self.instance and self.instance.pk else {}
        if "message_body_format" in config:
            self.fields["message_body_format"].initial = config["message_body_format"]
        self.fields["send_separately"].initial = bool(config.get("send_separately"))
        notificator_name = self.initial.get("notificator_name") or getattr(self.instance, "notificator_name", "")
        for form_field, config_key in NOTIFICATOR_TYPE_FIELDS.get(notificator_name, []):
            if config_key in config:
                self.fields[form_field].initial = config[config_key]

    def has_changed(self) -> bool:
        # Deliberately NOT the generic field-by-field has_changed(): that flags a row as
        # "changed" (forcing full validation, incl. a spurious required-field error) the moment
        # ANY field differs from its initial value -- including fields the user never touched,
        # e.g. the "enabled" checkbox (pre-checked True vs. an absent-checkbox-reads-False
        # mismatch) or a hidden type-specific field whose default value changes in a future code
        # update while an old page is still open. clean() already treats notificator_name as the
        # single source of truth for "is this row worth validating" -- reuse that here so an
        # untouched extra row is only ever considered "changed" for the one reason that matters.
        data = self.data if self.is_bound else {}
        value = self.fields["notificator_name"].widget.value_from_datadict(
            data, self.files, self.add_prefix("notificator_name")
        )
        return bool(value)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned

        notificator_name = cleaned.get("notificator_name")
        if not notificator_name:
            return cleaned

        if not cleaned.get("message_body_format"):
            self.add_error("message_body_format", "This field is required.")

        for form_field in NOTIFICATOR_REQUIRED_FIELDS.get(notificator_name, []):
            if not cleaned.get(form_field):
                self.add_error(form_field, "This field is required for the selected notificator.")

        return cleaned

    def save(self, commit=True):
        notificator_name = self.cleaned_data.get("notificator_name")
        config: dict[str, str | bool] = {}

        if self.cleaned_data.get("message_body_format"):
            config["message_body_format"] = self.cleaned_data["message_body_format"]
        if self.cleaned_data.get("send_separately"):
            config["send_separately"] = True

        for form_field, config_key in NOTIFICATOR_TYPE_FIELDS.get(notificator_name, []):
            value = self.cleaned_data.get(form_field)
            if value:
                config[config_key] = value

        self.instance.config = config
        return super().save(commit=commit)

    @property
    def is_blank_extra(self) -> bool:
        """True for a not-yet-saved row with nothing worth showing on page load."""
        if self.instance.pk or self.errors:
            return False
        return not self.has_changed()


# extra=3: a small pool of blank rows rendered hidden in the template and revealed one at a
# time by the "+ Add notification" button's JS, rather than one empty form always on display.
QueryNotificationConfigFormSet = inlineformset_factory(
    Query,
    QueryNotificationConfig,
    form=QueryNotificationConfigForm,
    extra=3,
    can_delete=True,
)
