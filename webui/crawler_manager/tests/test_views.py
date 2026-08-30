import pytest
from django.urls import reverse

from crawler_manager import scheduling
from crawler_manager.models import Query

pytestmark = pytest.mark.django_db


def _formset_management_data():
    return {
        "notification_configs-TOTAL_FORMS": "0",
        "notification_configs-INITIAL_FORMS": "0",
        "notification_configs-MIN_NUM_FORMS": "0",
        "notification_configs-MAX_NUM_FORMS": "1000",
    }


def test_query_list_requires_login(client) -> None:
    response = client.get(reverse("query_list"))
    assert response.status_code == 302


def test_query_list_shows_queries(admin_client) -> None:
    Query.objects.create(name="q1", spider_name="example", url="https://example.com")
    response = admin_client.get(reverse("query_list"))
    assert response.status_code == 200
    assert b"q1" in response.content


def test_query_create_creates_query(admin_client) -> None:
    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "cron_schedule": "",
        "is_active": "on",
        **_formset_management_data(),
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 302
    assert Query.objects.filter(name="new_query").exists()


def test_query_run_now_triggers_manual_run(admin_client, monkeypatch) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")

    calls = []
    monkeypatch.setattr(scheduling, "trigger_manual_run", lambda q: calls.append(q.id))

    response = admin_client.post(reverse("query_run_now", args=[query.pk]))

    assert response.status_code == 200
    assert calls == [query.id]


def test_query_delete_removes_query(admin_client) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")

    response = admin_client.post(reverse("query_delete", args=[query.pk]))

    assert response.status_code == 302
    assert not Query.objects.filter(pk=query.pk).exists()
