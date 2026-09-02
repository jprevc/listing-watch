from django.contrib import admin

from crawler_manager.models import CrawlRun, FoundItem, Query, QueryNotificationConfig


class QueryNotificationConfigInline(admin.TabularInline):
    model = QueryNotificationConfig
    extra = 1


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "spider_name", "url", "schedule_mode", "cron_schedule", "is_active", "updated_at")
    list_filter = ("user", "spider_name", "is_active")
    search_fields = ("name", "url")
    inlines = [QueryNotificationConfigInline]


@admin.register(FoundItem)
class FoundItemAdmin(admin.ModelAdmin):
    list_display = ("spider_name", "query_name", "user", "title", "price", "first_seen_at")
    list_filter = ("spider_name", "query_name", "user")
    search_fields = ("title", "url")
    date_hierarchy = "first_seen_at"


@admin.register(CrawlRun)
class CrawlRunAdmin(admin.ModelAdmin):
    list_display = (
        "query_name",
        "user",
        "spider_name",
        "trigger",
        "status",
        "started_at",
        "finished_at",
        "items_found_count",
        "new_items_count",
    )
    list_filter = ("status", "trigger", "spider_name", "user")
    search_fields = ("query_name", "error_message")
    date_hierarchy = "started_at"
