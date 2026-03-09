from django.contrib import admin

from .models import Badge, Genre, Role, UserBadge, UserProfile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["name", "display_name"]
    search_fields = ["name", "display_name"]


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "display_name", "reputation_score"]
    search_fields = ["user__username", "display_name"]
    filter_horizontal = ["roles", "genres"]
    readonly_fields = ["reputation_score", "created_at", "updated_at"]


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["name", "condition"]
    search_fields = ["name"]


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ["user", "badge", "awarded_at"]
    list_filter = ["badge"]
    search_fields = ["user__username"]
