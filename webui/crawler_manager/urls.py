from django.urls import path

from crawler_manager import views

urlpatterns = [
    path("", views.query_list, name="query_list"),
    path("queries/new/", views.query_create, name="query_create"),
    path("queries/<int:pk>/edit/", views.query_edit, name="query_edit"),
    path("queries/<int:pk>/delete/", views.query_delete, name="query_delete"),
    path("queries/<int:pk>/run/", views.query_run_now, name="query_run_now"),
    path("queries/<int:pk>/run-status/", views.query_run_status, name="query_run_status"),
    path("items/", views.found_item_list, name="found_item_list"),
    path("runs/", views.run_history_list, name="run_history_list"),
]
