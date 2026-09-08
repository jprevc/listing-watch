from django.urls import path

from crawler_manager import views

urlpatterns = [
    path("", views.query_list, name="query_list"),
    path("queries/new/", views.query_create, name="query_create"),
    path("queries/<int:pk>/edit/", views.query_edit, name="query_edit"),
    path("queries/<int:pk>/delete/", views.query_delete, name="query_delete"),
    path("queries/<int:pk>/run/", views.query_run_now, name="query_run_now"),
    path("queries/<int:pk>/stop/", views.query_stop_run, name="query_stop_run"),
    path("queries/<int:pk>/run-status/", views.query_run_status, name="query_run_status"),
    path("profiles/", views.profile_list, name="profile_list"),
    path("profiles/new/", views.profile_create, name="profile_create"),
    path("profiles/<int:pk>/edit/", views.profile_edit, name="profile_edit"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="profile_delete"),
    path("profiles/<int:pk>/test/", views.profile_test, name="profile_test"),
    path("profiles/options/", views.profile_options, name="profile_options"),
    path("items/", views.found_item_list, name="found_item_list"),
    path("runs/", views.run_history_list, name="run_history_list"),
]
