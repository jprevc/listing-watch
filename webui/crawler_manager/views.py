from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from crawler_manager import scheduling
from crawler_manager.forms import NotificationProfileForm, QueryForm, query_notification_formset_class
from crawler_manager.models import DEFAULT_MESSAGE_BODY_FORMAT, CrawlRun, FoundItem, NotificationProfile, Query
from crawler_manager.registry import available_spider_choices, spider_item_fields

PAGE_SIZE = 25

QueryNotificationConfigFormSet = query_notification_formset_class()


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


def _visible_profiles(request):
    # Unlike queries/runs/items, profiles hold live credentials (ntfy tokens, pushover app
    # tokens, email passwords) -- these stay private to their owner, with no staff-sees-all
    # exception.
    return NotificationProfile.objects.filter(user=request.user)


@login_required
def query_list(request):
    queries = _visible_queries(request).prefetch_related("notification_configs")
    return render(request, "crawler_manager/query_list.html", {"queries": queries})


@login_required
@require_http_methods(["GET", "POST"])
def query_create(request):
    if request.method == "POST":
        form = QueryForm(request.POST)
        formset = QueryNotificationConfigFormSet(request.POST, form_kwargs={"user": request.user})
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
        # Auto-attach this user's default profiles as pre-selected (but still removable) rows,
        # rather than a silent, invisible attachment -- see the formset's `extra` count below,
        # which grows to fit them alongside the usual 3 spare blank rows for manual "+ Add".
        default_profiles = list(_visible_profiles(request).filter(is_default=True))
        formset_class = query_notification_formset_class(extra=3 + len(default_profiles))
        formset = formset_class(
            initial=[
                {"profile": profile.pk, "message_body_format": DEFAULT_MESSAGE_BODY_FORMAT}
                for profile in default_profiles
            ],
            form_kwargs={"user": request.user},
        )
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
        formset = QueryNotificationConfigFormSet(request.POST, instance=query, form_kwargs={"user": request.user})
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"Query '{query.name}' updated.")
            return redirect("query_list")
    else:
        form = QueryForm(instance=query)
        formset = QueryNotificationConfigFormSet(instance=query, form_kwargs={"user": request.user})
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
def profile_list(request):
    profiles = _visible_profiles(request)
    return render(request, "crawler_manager/profile_list.html", {"profiles": profiles})


@login_required
@require_http_methods(["GET", "POST"])
def profile_create(request):
    if request.method == "POST":
        form = NotificationProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, f"Notification profile '{profile.name}' created.")
            return redirect("profile_list")
    else:
        form = NotificationProfileForm()
    return render(request, "crawler_manager/profile_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request, pk):
    profile = get_object_or_404(_visible_profiles(request), pk=pk)
    if request.method == "POST":
        form = NotificationProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Notification profile '{profile.name}' updated.")
            return redirect("profile_list")
    else:
        form = NotificationProfileForm(instance=profile)
    return render(request, "crawler_manager/profile_form.html", {"form": form, "profile": profile})


@login_required
@require_POST
def profile_delete(request, pk):
    profile = get_object_or_404(_visible_profiles(request), pk=pk)
    try:
        profile.delete()
    except ProtectedError as exc:
        query_names = sorted({attachment.query.name for attachment in exc.protected_objects})
        messages.error(
            request,
            f"Can't delete '{profile.name}' -- still used by: {', '.join(query_names)}. "
            "Remove it from those queries first.",
        )
        return redirect("profile_list")
    messages.success(request, f"Notification profile '{profile.name}' deleted.")
    return redirect("profile_list")


@login_required
def profile_options(request):
    """
    JSON list of the current user's profiles, for the "Refresh" button on the query form to pick
    up a profile just created in another tab without reloading (and losing) the query form.
    """
    profiles = _visible_profiles(request).values("pk", "name", "notificator_name")
    return JsonResponse({"profiles": list(profiles)})


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
