"""
Django admin configuration for the moderation app.
Provides enhanced views for Flag and ModerationAction with filters and inline actions.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Flag, ModerationAction


class ModerationActionInline(admin.TabularInline):
    model = ModerationAction
    extra = 0
    readonly_fields = ("moderator", "action_type", "notes", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Flag)
class FlagAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "content_label",
        "reason",
        "status",
        "reporter",
        "created_at",
        "action_count",
    )
    list_filter = ("status", "reason", "created_at", "content_type")
    search_fields = ("reporter__username", "description", "object_id")
    readonly_fields = (
        "reporter",
        "content_type",
        "object_id",
        "reason",
        "description",
        "created_at",
        "updated_at",
    )
    list_select_related = ("reporter", "content_type")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = [ModerationActionInline]

    fieldsets = (
        (
            _("Reporte"),
            {
                "fields": (
                    "reporter",
                    "content_type",
                    "object_id",
                    "reason",
                    "description",
                )
            },
        ),
        (
            _("Estado"),
            {
                "fields": ("status", "created_at", "updated_at"),
            },
        ),
    )

    @admin.display(description=_("Contenido"))
    def content_label(self, obj):
        return format_html(
            '<span style="font-family:monospace">{} #{}</span>',
            obj.content_type.model,
            obj.object_id,
        )

    @admin.display(description=_("Acciones"))
    def action_count(self, obj):
        count = obj.actions.count()
        return count if count else "—"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("actions")


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "flag_link",
        "action_type",
        "moderator",
        "created_at",
        "notes_short",
    )
    list_filter = ("action_type", "created_at")
    search_fields = ("moderator__username", "notes", "flag__object_id")
    readonly_fields = ("flag", "moderator", "action_type", "notes", "created_at")
    list_select_related = ("moderator", "flag", "flag__content_type")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    @admin.display(description=_("Reporte"))
    def flag_link(self, obj):
        return format_html(
            "Flag #{} — {} #{}",
            obj.flag_id,
            obj.flag.content_type.model,
            obj.flag.object_id,
        )

    @admin.display(description=_("Notas"))
    def notes_short(self, obj):
        if obj.notes:
            return obj.notes[:60] + ("…" if len(obj.notes) > 60 else "")
        return "—"
