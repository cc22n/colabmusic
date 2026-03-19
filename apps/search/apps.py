"""
Search app configuration.

Registers models with django-watson in the ready() hook so they are indexed
for full-text search. Each model gets a SearchAdapter subclass that controls:
  - which queryset is indexed (live_queryset filters out private/hidden content)
  - what text is stored as title / description / url in the search index
"""

from django.apps import AppConfig
from watson.search import SearchAdapter


# ---------------------------------------------------------------------------
# SearchAdapter subclasses
# (defined at module level; models are imported lazily inside each method
#  to avoid circular imports during app startup)
# ---------------------------------------------------------------------------


class ProjectSearchAdapter(SearchAdapter):
    """Index public, non-archived projects. Includes tag names in content."""

    fields = ("title", "description")

    def get_live_queryset(self):
        from apps.projects.models import Project, ProjectStatus

        return (
            Project.objects.filter(is_public=True)
            .exclude(status=ProjectStatus.ARCHIVED)
            .select_related("genre")
            .prefetch_related("tags")
        )

    def get_title(self, obj):
        return obj.title

    def get_description(self, obj):
        return (obj.description or "")[:200]

    def get_url(self, obj):
        return obj.get_absolute_url()

    def get_content(self, obj):
        tag_names = " ".join(obj.tags.values_list("name", flat=True))
        genre_name = obj.genre.name if obj.genre else ""
        return f"{obj.title} {obj.description or ''} {tag_names} {genre_name}"


class LyricsSearchAdapter(SearchAdapter):
    """Index non-hidden lyrics; url points to parent project."""

    fields = ("content", "original_artist", "original_song")

    def get_live_queryset(self):
        from apps.projects.models import Lyrics

        return Lyrics.objects.filter(is_hidden=False).select_related(
            "project", "author"
        )

    def get_title(self, obj):
        return f"Letra — {obj.project.title}"

    def get_description(self, obj):
        return (obj.content or "")[:200]

    def get_url(self, obj):
        return obj.project.get_absolute_url()


class BeatSearchAdapter(SearchAdapter):
    """Index non-hidden beats; url points to parent project."""

    fields = ("description",)

    def get_live_queryset(self):
        from apps.projects.models import Beat

        return Beat.objects.filter(is_hidden=False).select_related(
            "project", "producer"
        )

    def get_title(self, obj):
        return f"Beat de {obj.producer.username} — {obj.project.title}"

    def get_description(self, obj):
        return (obj.description or "")[:200]

    def get_url(self, obj):
        return obj.project.get_absolute_url()


class UserProfileSearchAdapter(SearchAdapter):
    """Index all user profiles (public by default)."""

    fields = ("display_name", "bio")

    def get_title(self, obj):
        return str(obj)

    def get_description(self, obj):
        return (obj.bio or "")[:200]

    def get_url(self, obj):
        return obj.get_absolute_url()


# ---------------------------------------------------------------------------
# App config
# ---------------------------------------------------------------------------


class SearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.search"
    verbose_name = "Búsqueda"

    def ready(self):
        """Register models with watson after all apps have loaded."""
        from watson.search import register

        from apps.accounts.models import UserProfile
        from apps.projects.models import Beat, Lyrics, Project

        register(Project, ProjectSearchAdapter)
        register(Lyrics, LyricsSearchAdapter)
        register(Beat, BeatSearchAdapter)
        register(UserProfile, UserProfileSearchAdapter)
