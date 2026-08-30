"""
URL configuration for the news_crawlers web UI project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("crawler_manager.urls")),
]
