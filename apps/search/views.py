"""
Search views for ColabMusic.

SearchView     — full search page at /search/
search_results — HTMX partial at /search/results/ (also used by navbar dropdown)
"""

from watson.search import search as watson_search
from django.apps import apps as django_apps
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils.html import strip_tags
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.accounts.models import Genre

# Maps URL "type" param → (app_label, ModelName)
_TYPE_APP = {
    "project": ("projects", "Project"),
    "lyrics": ("projects", "Lyrics"),
    "beat": ("projects", "Beat"),
    "user": ("accounts", "UserProfile"),
}


def _get_model(type_key):
    """Return the model class for a type_key string, or None."""
    entry = _TYPE_APP.get(type_key)
    if entry is None:
        return None
    app_label, model_name = entry
    return django_apps.get_model(app_label, model_name)


# ---------------------------------------------------------------------------
# Full search page
# ---------------------------------------------------------------------------


class SearchView(TemplateView):
    """
    Renders the main search page at /search/.
    Actual search is performed asynchronously by `search_results` HTMX partial.
    """

    template_name = "search/search.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["genres"] = Genre.objects.all().order_by("name")
        ctx["current_type"] = self.request.GET.get("type", "")
        ctx["current_genre"] = self.request.GET.get("genre", "")
        return ctx


# ---------------------------------------------------------------------------
# HTMX results partial (also serves navbar dropdown with ?limit=5)
# ---------------------------------------------------------------------------


@require_GET
def search_results(request):
    """
    HTMX endpoint — returns the search/partials/results.html fragment.

    Query params:
      q      — search query (stripped, max 200 chars)
      type   — filter: "project" | "lyrics" | "beat" | "user"  (optional)
      genre  — genre slug, only effective when type=project (optional)
      limit  — integer; when set returns compact dropdown view for navbar
      page   — page number for paginated full results
    """
    if not request.headers.get("HX-Request"):
        return HttpResponseBadRequest("Solo peticiones HTMX.")

    # Sanitise query
    q = strip_tags(request.GET.get("q", "")).strip()[:200]
    type_filter = request.GET.get("type", "").strip()
    genre_slug = request.GET.get("genre", "").strip()

    try:
        limit = int(request.GET.get("limit", 0))
        limit = max(0, min(limit, 20))  # clamp 0–20
    except (ValueError, TypeError):
        limit = 0

    # Empty query — return blank partial
    if not q:
        return render(
            request,
            "search/partials/results.html",
            {"results": [], "q": q, "empty_query": True},
        )

    # Build models_arg for watson.search()
    models_arg = _build_models_arg(type_filter, genre_slug)
    results = watson_search(q, models=models_arg)

    is_dropdown = bool(limit)

    if is_dropdown:
        results = results[:limit]
        return render(
            request,
            "search/partials/results.html",
            {
                "results": results,
                "q": q,
                "is_dropdown": True,
                "empty_query": False,
            },
        )

    # Full paginated results (order_by silences UnorderedObjectListWarning)
    page_obj = Paginator(results.order_by(), 10).get_page(request.GET.get("page", 1))
    return render(
        request,
        "search/partials/results.html",
        {
            "results": page_obj,
            "q": q,
            "is_dropdown": False,
            "type_filter": type_filter,
            "genre_slug": genre_slug,
            "empty_query": False,
        },
    )


def _build_models_arg(type_filter, genre_slug):
    """
    Build the models list to pass to watson.search().
    Returns [] (search all registered models) when type_filter is empty/unknown.
    """
    if not type_filter or type_filter not in _TYPE_APP:
        return []

    if type_filter == "project" and genre_slug:
        from apps.projects.models import Project, ProjectStatus

        return [
            Project.objects.filter(
                is_public=True, genre__slug=genre_slug
            ).exclude(status=ProjectStatus.ARCHIVED)
        ]

    model_cls = _get_model(type_filter)
    return [model_cls] if model_cls else []
