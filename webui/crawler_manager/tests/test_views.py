import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from crawler_manager import scheduling
from crawler_manager.models import CrawlRun, FoundItem, NotificationProfile, Query, QueryNotificationConfig
from listing_watch import notificators

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


def test_query_create_attaches_selected_profile(admin_client, django_user_model) -> None:
    user = django_user_model.objects.get(username="admin")
    profile = NotificationProfile.objects.create(
        user=user, name="My ntfy", notificator_name="ntfy", config={"topic": "t"}
    )

    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "schedule_mode": "manual",
        "is_active": "on",
        "notification_configs-TOTAL_FORMS": "1",
        "notification_configs-INITIAL_FORMS": "0",
        "notification_configs-MIN_NUM_FORMS": "0",
        "notification_configs-MAX_NUM_FORMS": "1000",
        "notification_configs-0-profile": str(profile.pk),
        "notification_configs-0-message_body_format": "{title}",
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 302
    query = Query.objects.get(name="new_query")
    assert query.notification_configs.filter(profile=profile).exists()


def test_query_create_rejects_another_users_profile(admin_client, django_user_model) -> None:
    other = django_user_model.objects.create_user(username="other", password="pw")
    other_profile = NotificationProfile.objects.create(
        user=other, name="Theirs", notificator_name="ntfy", config={"topic": "t"}
    )

    data = {
        "name": "new_query",
        "spider_name": "example",
        "url": "https://example.com/search",
        "schedule_mode": "manual",
        "is_active": "on",
        "notification_configs-TOTAL_FORMS": "1",
        "notification_configs-INITIAL_FORMS": "0",
        "notification_configs-MIN_NUM_FORMS": "0",
        "notification_configs-MAX_NUM_FORMS": "1000",
        "notification_configs-0-profile": str(other_profile.pk),
        "notification_configs-0-message_body_format": "{title}",
    }
    response = admin_client.post(reverse("query_create"), data)

    assert response.status_code == 200
    assert not Query.objects.filter(name="new_query").exists()


def test_query_create_get_preselects_default_profiles(admin_client, django_user_model) -> None:
    user = django_user_model.objects.get(username="admin")
    default_profile = NotificationProfile.objects.create(
        user=user, name="Default ntfy", notificator_name="ntfy", config={"topic": "t"}, is_default=True
    )
    NotificationProfile.objects.create(user=user, name="Not default", notificator_name="email", config={})

    response = admin_client.get(reverse("query_create"))

    formset = response.context["formset"]
    preselected = [f.initial.get("profile") for f in formset.forms if f.initial.get("profile")]
    assert preselected == [default_profile.pk]


def test_profile_list_requires_login(client) -> None:
    response = client.get(reverse("profile_list"))
    assert response.status_code == 302


def test_profile_list_only_shows_own_profiles(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    NotificationProfile.objects.create(user=owner, name="Mine", notificator_name="ntfy", config={"topic": "t"})
    NotificationProfile.objects.create(user=other, name="Theirs", notificator_name="ntfy", config={"topic": "t"})

    client.force_login(owner)
    response = client.get(reverse("profile_list"))

    content = response.content.decode()
    assert "Mine" in content
    assert "Theirs" not in content


def test_profile_list_hides_other_users_profiles_even_for_staff(admin_client, django_user_model) -> None:
    other = django_user_model.objects.create_user(username="other", password="pw")
    NotificationProfile.objects.create(user=other, name="Theirs", notificator_name="ntfy", config={"topic": "t"})

    response = admin_client.get(reverse("profile_list"))

    assert b"Theirs" not in response.content


def test_profile_create_sets_owner_and_config(admin_client, django_user_model) -> None:
    data = {"name": "My ntfy", "notificator_name": "ntfy", "topic": "my-topic"}
    response = admin_client.post(reverse("profile_create"), data)

    assert response.status_code == 302
    profile = NotificationProfile.objects.get(name="My ntfy")
    assert profile.user == django_user_model.objects.get(username="admin")
    assert profile.config == {"topic": "my-topic"}


def test_profile_create_requires_type_specific_fields(admin_client) -> None:
    data = {"name": "My ntfy", "notificator_name": "ntfy"}  # missing required "topic"
    response = admin_client.post(reverse("profile_create"), data)

    assert response.status_code == 200
    assert not NotificationProfile.objects.filter(name="My ntfy").exists()


def test_profile_edit_404s_for_non_owner(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    profile = NotificationProfile.objects.create(
        user=owner, name="Mine", notificator_name="ntfy", config={"topic": "t"}
    )

    client.force_login(other)
    response = client.get(reverse("profile_edit", args=[profile.pk]))

    assert response.status_code == 404


def test_profile_delete_removes_unused_profile(admin_client, django_user_model) -> None:
    user = django_user_model.objects.get(username="admin")
    profile = NotificationProfile.objects.create(user=user, name="Mine", notificator_name="ntfy", config={"topic": "t"})

    response = admin_client.post(reverse("profile_delete", args=[profile.pk]))

    assert response.status_code == 302
    assert not NotificationProfile.objects.filter(pk=profile.pk).exists()


def test_profile_delete_blocked_when_attached_to_a_query(admin_client, django_user_model) -> None:
    user = django_user_model.objects.get(username="admin")
    profile = NotificationProfile.objects.create(user=user, name="Mine", notificator_name="ntfy", config={"topic": "t"})
    query = Query.objects.create(name="q1", spider_name="example", url="https://example.com", user=user)
    QueryNotificationConfig.objects.create(query=query, profile=profile, message_body_format="{title}")

    response = admin_client.post(reverse("profile_delete", args=[profile.pk]))

    assert response.status_code == 302
    assert NotificationProfile.objects.filter(pk=profile.pk).exists()


def test_profile_test_sends_via_the_profiles_own_notificator_and_config(admin_client, django_user_model, monkeypatch) -> None:
    user = django_user_model.objects.get(username="admin")
    profile = NotificationProfile.objects.create(
        user=user, name="Mine", notificator_name="ntfy", config={"topic": "my-topic"}
    )
    calls = []
    monkeypatch.setattr(
        notificators.NtfyNotificator,
        "send_text",
        lambda self, subject, message: calls.append((self.configuration, subject, message)),
    )

    response = admin_client.post(reverse("profile_test", args=[profile.pk]))

    assert response.status_code == 302
    assert len(calls) == 1
    sent_config, subject, message = calls[0]
    assert sent_config == {"topic": "my-topic"}
    assert "test" in subject.lower()
    assert profile.name in message
    [message_obj] = get_messages(response.wsgi_request)
    assert message_obj.level_tag == "success"


def test_profile_test_shows_failure_as_an_error_message(admin_client, django_user_model, monkeypatch) -> None:
    user = django_user_model.objects.get(username="admin")
    profile = NotificationProfile.objects.create(
        user=user, name="Mine", notificator_name="ntfy", config={"topic": "my-topic"}
    )

    def _raise(self, subject, message):
        raise RuntimeError("boom")

    monkeypatch.setattr(notificators.NtfyNotificator, "send_text", _raise)

    response = admin_client.post(reverse("profile_test", args=[profile.pk]))

    assert response.status_code == 302
    [message_obj] = get_messages(response.wsgi_request)
    assert message_obj.level_tag == "error"
    assert "boom" in str(message_obj)


def test_profile_test_404s_for_non_owner(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    profile = NotificationProfile.objects.create(
        user=owner, name="Mine", notificator_name="ntfy", config={"topic": "t"}
    )

    client.force_login(other)
    response = client.post(reverse("profile_test", args=[profile.pk]))

    assert response.status_code == 404


def test_profile_test_requires_post(admin_client, django_user_model) -> None:
    user = django_user_model.objects.get(username="admin")
    profile = NotificationProfile.objects.create(user=user, name="Mine", notificator_name="ntfy", config={"topic": "t"})

    response = admin_client.get(reverse("profile_test", args=[profile.pk]))

    assert response.status_code == 405


def test_setting_a_profile_as_default_via_edit_clears_the_previous_default(admin_client, django_user_model) -> None:
    user = django_user_model.objects.get(username="admin")
    first = NotificationProfile.objects.create(
        user=user, name="First", notificator_name="ntfy", config={"topic": "t"}, is_default=True
    )
    second = NotificationProfile.objects.create(
        user=user, name="Second", notificator_name="ntfy", config={"topic": "t2"}
    )

    response = admin_client.post(
        reverse("profile_edit", args=[second.pk]),
        {"name": "Second", "notificator_name": "ntfy", "topic": "t2", "is_default": "on"},
    )

    assert response.status_code == 302
    first.refresh_from_db()
    assert first.is_default is False
    second.refresh_from_db()
    assert second.is_default is True


def test_profile_options_json_only_lists_own_profiles(client, django_user_model) -> None:
    owner = django_user_model.objects.create_user(username="owner", password="pw")
    other = django_user_model.objects.create_user(username="other", password="pw")
    NotificationProfile.objects.create(user=owner, name="Mine", notificator_name="ntfy", config={"topic": "t"})
    NotificationProfile.objects.create(user=other, name="Theirs", notificator_name="ntfy", config={"topic": "t"})

    client.force_login(owner)
    response = client.get(reverse("profile_options"))

    names = [p["name"] for p in response.json()["profiles"]]
    assert names == ["Mine"]


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
