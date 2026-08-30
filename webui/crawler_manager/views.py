from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from crawler_manager import scheduling
from crawler_manager.forms import QueryForm, QueryNotificationConfigFormSet
from crawler_manager.models import Query


@login_required
def query_list(request):
    queries = Query.objects.prefetch_related("notification_configs").all()
    return render(request, "crawler_manager/query_list.html", {"queries": queries})


@login_required
@require_http_methods(["GET", "POST"])
def query_create(request):
    if request.method == "POST":
        form = QueryForm(request.POST)
        formset = QueryNotificationConfigFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            query = form.save()
            formset.instance = query
            formset.save()
            messages.success(request, f"Query '{query.name}' created.")
            return redirect("query_list")
    else:
        form = QueryForm()
        formset = QueryNotificationConfigFormSet()
    return render(request, "crawler_manager/query_form.html", {"form": form, "formset": formset})


@login_required
@require_http_methods(["GET", "POST"])
def query_edit(request, pk):
    query = get_object_or_404(Query, pk=pk)
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
    return render(request, "crawler_manager/query_form.html", {"form": form, "formset": formset, "query": query})


@login_required
@require_POST
def query_delete(request, pk):
    query = get_object_or_404(Query, pk=pk)
    query.delete()
    messages.success(request, f"Query '{query.name}' deleted.")
    return redirect("query_list")


@login_required
@require_POST
def query_run_now(request, pk):
    query = get_object_or_404(Query, pk=pk)
    scheduling.trigger_manual_run(query)
    return render(request, "crawler_manager/_run_status_badge.html", {"query": query, "just_triggered": True})


@login_required
def query_run_status(request, pk):
    query = get_object_or_404(Query, pk=pk)
    just_triggered = request.GET.get("just_triggered") == "1"
    return render(request, "crawler_manager/_run_status_badge.html", {"query": query, "just_triggered": just_triggered})
