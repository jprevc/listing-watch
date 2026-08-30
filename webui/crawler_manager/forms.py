from django import forms
from django.forms import inlineformset_factory

from crawler_manager.models import Query, QueryNotificationConfig


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
        fields = ["notificator_name", "config", "enabled"]
        widgets = {
            "config": forms.Textarea(attrs={"rows": 4, "placeholder": '{"topic": "...", "message_body_format": "..."}'}),
        }


QueryNotificationConfigFormSet = inlineformset_factory(
    Query,
    QueryNotificationConfig,
    form=QueryNotificationConfigForm,
    extra=1,
    can_delete=True,
)
