from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from crawler_manager import scheduling
from crawler_manager.forms import QueryForm, QueryNotificationConfigFormSet
from crawler_manager.models import CrawlRun, FoundItem, Query
from crawler_manager.registry import available_spider_choices, spider_item_fields

PAGE_SIZE = 25


def _visible_queries(request):
    """Staff see every user's queries; everyone else only sees their own."""
    if request.user.is_staff:
        return Query.objects.all()
    return Query.objects.filter(user=request.user)


def _visible_runs(request):
    if request.user.is_staff:
        return CrawlRun.objects.all()
    return CrawlRun.objects.filter(user=request.user)


def _visible_items(request):
    if request.user.is_staff:
        return FoundItem.objects.all()
    return FoundItem.objects.filter(user=request.user)


@login_required
def query_list(request):
    queries = _visible_queries(request).prefetch_related("notification_configs")
    return render(request, "crawler_manager/query_list.html", {"queries": queries})


@login_required
@require_http_methods(["GET", "POST"])
def query_create(request):
    if request.method == "POST":
        form = QueryForm(request.POST)
        formset = QueryNotificationConfigFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            query = form.save(commit=False)
            query.user = request.user
            query.save()
            formset.instance = query
            formset.save()
            messages.success(request, f"Query '{query.name}' created.")
            return redirect("query_list")
    else:
        form = QueryForm()
        formset = QueryNotificationConfigFormSet()
    return render(
        request,
        "crawler_manager/query_form.html",
        {"form": form, "formset": formset, "spider_item_fields": spider_item_fields()},
    )


@login_required
@require_http_methods(["GET", "POST"])
def query_edit(request, pk):
    query = get_object_or_404(_visible_queries(request), pk=pk)
    if request.method == "POST":
        form = QueryForm(request.POST, instance=query)
        formset = QueryNotificationConfigFormSet(request.POST, instance=query)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"Query '{query.name}' updated.")
            return redirect("query_list")
    else:
        form = QueryForm(instance=query)
        formset = QueryNotificationConfigFormSet(instance=query)
    return render(
        request,
        "crawler_manager/query_form.html",
        {"form": form, "formset": formset, "query": query, "spider_item_fields": spider_item_fields()},
    )


@login_required
@require_POST
def query_delete(request, pk):
    query = get_object_or_404(_visible_queries(request), pk=pk)
    query.delete()
    messages.success(request, f"Query '{query.name}' deleted.")
    return redirect("query_list")


@login_required
@require_POST
def query_run_now(request, pk):
    query = get_object_or_404(_visible_queries(request), pk=pk)
    scheduling.trigger_manual_run(query)
    return render(request, "crawler_manager/_run_status_response.html", {"query": query, "just_triggered": True})


@login_required
@require_POST
def query_stop_run(request, pk):
    query = get_object_or_404(_visible_queries(request), pk=pk)
    # A no-op if nothing is currently running (e.g. it already finished) -- the rendered badge
    # below just reflects whatever the real state turns out to be.
    CrawlRun.objects.filter(query=query, status=CrawlRun.Status.RUNNING).update(cancel_requested=True)
    return render(request, "crawler_manager/_run_status_response.html", {"query": query, "just_triggered": False})


@login_required
def query_run_status(request, pk):
    # Polled by the badge itself (see _run_status_badge.html) -- never "just triggered", so it
    # reflects only the real current CrawlRun state, and polling naturally stops once that
    # reaches success/failed.
    query = get_object_or_404(_visible_queries(request), pk=pk)
    return render(request, "crawler_manager/_run_status_response.html", {"query": query, "just_triggered": False})


@login_required
def found_item_list(request):
    items = _visible_items(request)

    selected_spider = request.GET.get("spider", "")
    if selected_spider:
        items = items.filter(spider_name=selected_spider)

    selected_query = request.GET.get("query", "")
    if selected_query:
        items = items.filter(query_name=selected_query)

    # Linked in from the run history panel's "Found"/"New" counts for one specific run. "New"
    # means first created by that run (the `run` FK); "Found" means encountered by that run at
    # all, new or already-seen (the `last_seen_run` FK, updated on every run that re-matches an
    # existing item -- see services._persist_and_diff).
    run_filter = None
    selected_run = request.GET.get("run", "")
    selected_run_kind = request.GET.get("run_kind", "") if selected_run else ""
    if selected_run:
        if selected_run_kind == "new":
            items = items.filter(run_id=selected_run)
        else:
            selected_run_kind = "found"
            items = items.filter(last_seen_run_id=selected_run)
        run_filter = get_object_or_404(_visible_runs(request), pk=selected_run)

    page_obj = Paginator(items, PAGE_SIZE).get_page(request.GET.get("page"))
    query_names = _visible_items(request).order_by("query_name").values_list("query_name", flat=True).distinct()

    return render(
        request,
        "crawler_manager/found_item_list.html",
        {
            "page_obj": page_obj,
            "spider_choices": available_spider_choices(),
            "query_names": query_names,
            "selected_spider": selected_spider,
            "selected_query": selected_query,
            "run_filter": run_filter,
            "selected_run_kind": selected_run_kind,
        },
    )


@login_required
def run_history_list(request):
    runs = _visible_runs(request)

    selected_status = request.GET.get("status", "")
    if selected_status:
        runs = runs.filter(status=selected_status)

    selected_query = request.GET.get("query", "")
    if selected_query:
        runs = runs.filter(query_name=selected_query)

    page_obj = Paginator(runs, PAGE_SIZE).get_page(request.GET.get("page"))
    query_names = _visible_runs(request).order_by("query_name").values_list("query_name", flat=True).distinct()

    return render(
        request,
        "crawler_manager/run_history_list.html",
        {
            "page_obj": page_obj,
            "status_choices": CrawlRun.Status.choices,
            "selected_status": selected_status,
            "query_names": query_names,
            "selected_query": selected_query,
        },
    )
