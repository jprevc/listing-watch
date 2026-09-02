import pytest
from django.urls import reverse

from crawler_manager import scheduling
from crawler_manager.models import CrawlRun, FoundItem, Query

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
        "schedule_mode": "manual",
        "is_active": "on",
        **_formset_management_data(),
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 302
    assert Query.objects.filter(name="new_query").exists()


def test_query_create_sets_owner_to_current_user(admin_client, django_user_model) -> None:
    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "schedule_mode": "manual",
        "is_active": "on",
        **_formset_management_data(),
    }
    admin_client.post(reverse("query_create"), data)

    query = Query.objects.get(name="new_query")
    assert query.user == django_user_model.objects.get(username="admin")


def test_query_create_simple_mode_derives_cron_schedule(admin_client) -> None:
    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "schedule_mode": "simple",
        "interval_value": "15",
        "interval_unit": "minutes",
        "is_active": "on",
        **_formset_management_data(),
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 302
    query = Query.objects.get(name="new_query")
    assert query.cron_schedule == "*/15 * * * *"


def test_query_create_simple_mode_rejects_value_below_floor(admin_client) -> None:
    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "schedule_mode": "simple",
        "interval_value": "1",
        "interval_unit": "minutes",
        "is_active": "on",
        **_formset_management_data(),
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 200
    assert not Query.objects.filter(name="new_query").exists()


def test_query_create_advanced_mode_requires_cron_schedule(admin_client) -> None:
    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "schedule_mode": "advanced",
        "cron_schedule": "",
        "is_active": "on",
        **_formset_management_data(),
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 200
    assert not Query.objects.filter(name="new_query").exists()


def test_query_list_only_shows_own_queries_for_non_staff(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    Query.objects.create(name="mine", spider_name="example", url="https://example.com", user=owner)
    Query.objects.create(name="not_mine", spider_name="example", url="https://example.com", user=other)

    client.force_login(owner)
    response = client.get(reverse("query_list"))

    assert b"mine" in response.content
    assert b"not_mine" not in response.content


def test_query_list_shows_all_queries_for_staff(admin_client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    Query.objects.create(name="someone_elses", spider_name="example", url="https://example.com", user=owner)

    response = admin_client.get(reverse("query_list"))

    assert b"someone_elses" in response.content


def test_query_edit_404s_for_non_owner(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com", user=owner)

    client.force_login(other)
    response = client.get(reverse("query_edit", args=[query.pk]))

    assert response.status_code == 404


def test_query_delete_404s_for_non_owner(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com", user=owner)

    client.force_login(other)
    response = client.post(reverse("query_delete", args=[query.pk]))

    assert response.status_code == 404
    assert Query.objects.filter(pk=query.pk).exists()


def test_query_run_now_triggers_manual_run(admin_client, monkeypatch) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")

    calls = []
    monkeypatch.setattr(scheduling, "trigger_manual_run", lambda q: calls.append(q.id))

    response = admin_client.post(reverse("query_run_now", args=[query.pk]))

    assert response.status_code == 200
    assert calls == [query.id]


def test_query_stop_run_sets_cancel_requested_on_running_run(admin_client) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")
    run = CrawlRun.objects.create(
        query=query, query_name=query.name, spider_name=query.spider_name,
        trigger=CrawlRun.Trigger.MANUAL, status=CrawlRun.Status.RUNNING,
    )

    response = admin_client.post(reverse("query_stop_run", args=[query.pk]))

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.cancel_requested is True


def test_query_stop_run_is_a_noop_without_a_running_run(admin_client) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")
    run = CrawlRun.objects.create(
        query=query, query_name=query.name, spider_name=query.spider_name,
        trigger=CrawlRun.Trigger.MANUAL, status=CrawlRun.Status.SUCCESS,
    )

    response = admin_client.post(reverse("query_stop_run", args=[query.pk]))

    assert response.status_code == 200
    run.refresh_from_db()
    assert run.cancel_requested is False


def test_query_delete_removes_query(admin_client) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")

    response = admin_client.post(reverse("query_delete", args=[query.pk]))

    assert response.status_code == 302
    assert not Query.objects.filter(pk=query.pk).exists()


def _make_item(
    query: Query, *, run: CrawlRun | None, last_seen_run: CrawlRun | None, suffix: str
) -> FoundItem:
    return FoundItem.objects.create(
        query=query,
        query_name=query.name,
        spider_name=query.spider_name,
        run=run,
        last_seen_run=last_seen_run,
        content_hash=f"hash-{suffix}",
        payload={},
        title=f"item-{suffix}",
    )


def test_found_item_list_run_kind_new_shows_only_items_created_by_that_run(admin_client) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")
    run = CrawlRun.objects.create(query=query, query_name=query.name, spider_name=query.spider_name, trigger=CrawlRun.Trigger.MANUAL)
    older_run = CrawlRun.objects.create(query=query, query_name=query.name, spider_name=query.spider_name, trigger=CrawlRun.Trigger.MANUAL)
    new_item = _make_item(query, run=run, last_seen_run=run, suffix="new")
    older_item = _make_item(query, run=older_run, last_seen_run=run, suffix="older")

    response = admin_client.get(reverse("found_item_list"), {"run": run.pk, "run_kind": "new"})

    content = response.content.decode()
    assert new_item.title in content
    assert older_item.title not in content


def test_found_item_list_run_kind_found_shows_new_and_reencountered_items(admin_client) -> None:
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com")
    run = CrawlRun.objects.create(query=query, query_name=query.name, spider_name=query.spider_name, trigger=CrawlRun.Trigger.MANUAL)
    older_run = CrawlRun.objects.create(query=query, query_name=query.name, spider_name=query.spider_name, trigger=CrawlRun.Trigger.MANUAL)
    new_item = _make_item(query, run=run, last_seen_run=run, suffix="new")
    reencountered_item = _make_item(query, run=older_run, last_seen_run=run, suffix="reencountered")
    unrelated_item = _make_item(query, run=older_run, last_seen_run=older_run, suffix="unrelated")

    response = admin_client.get(reverse("found_item_list"), {"run": run.pk, "run_kind": "found"})

    content = response.content.decode()
    assert new_item.title in content
    assert reencountered_item.title in content
    assert unrelated_item.title not in content


def test_found_item_list_only_shows_own_items_for_non_staff(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    my_query = Query.objects.create(name="mine", spider_name="example", url="https://example.com", user=owner)
    their_query = Query.objects.create(name="theirs", spider_name="example", url="https://example.com", user=other)
    my_item = FoundItem.objects.create(
        query=my_query, user=owner, query_name=my_query.name, spider_name=my_query.spider_name,
        content_hash="hash-mine", payload={}, title="my-item",
    )
    their_item = FoundItem.objects.create(
        query=their_query, user=other, query_name=their_query.name, spider_name=their_query.spider_name,
        content_hash="hash-theirs", payload={}, title="their-item",
    )

    client.force_login(owner)
    response = client.get(reverse("found_item_list"))

    content = response.content.decode()
    assert my_item.title in content
    assert their_item.title not in content


def test_run_history_list_only_shows_own_runs_for_non_staff(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    my_query = Query.objects.create(name="mine", spider_name="example", url="https://example.com", user=owner)
    their_query = Query.objects.create(name="theirs", spider_name="example", url="https://example.com", user=other)
    CrawlRun.objects.create(
        query=my_query, user=owner, query_name=my_query.name, spider_name=my_query.spider_name,
        trigger=CrawlRun.Trigger.MANUAL,
    )
    CrawlRun.objects.create(
        query=their_query, user=other, query_name=their_query.name, spider_name=their_query.spider_name,
        trigger=CrawlRun.Trigger.MANUAL,
    )

    client.force_login(owner)
    response = client.get(reverse("run_history_list"))

    content = response.content.decode()
    assert "mine" in content
    assert "theirs" not in content
