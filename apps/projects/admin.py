from django.contrib import admin

from .models import Beat, FinalMix, Lyrics, Project, Tag, VocalTrack


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "project_type", "status", "created_by", "is_public", "created_at"]
    list_filter = ["project_type", "status", "is_public", "genre"]
    search_fields = ["title", "created_by__username"]
    readonly_fields = ["slug", "created_at", "updated_at"]
    filter_horizontal = ["tags"]


@admin.register(Lyrics)
class LyricsAdmin(admin.ModelAdmin):
    list_display = ["project", "author", "language", "is_selected", "created_at"]
    list_filter = ["is_selected", "language"]
    search_fields = ["project__title", "author__username"]


@admin.register(Beat)
class BeatAdmin(admin.ModelAdmin):
    list_display = ["project", "producer", "bpm", "key_signature", "is_selected", "processing_status"]
    list_filter = ["is_selected", "processing_status"]
    search_fields = ["project__title", "producer__username"]


@admin.register(VocalTrack)
class VocalTrackAdmin(admin.ModelAdmin):
    list_display = ["project", "vocalist", "version_number", "is_selected", "processing_status"]
    list_filter = ["is_selected", "processing_status"]
    search_fields = ["project__title", "vocalist__username"]


@admin.register(FinalMix)
class FinalMixAdmin(admin.ModelAdmin):
    list_display = ["project", "play_count", "is_featured", "processing_status"]
    list_filter = ["is_featured", "processing_status"]
    search_fields = ["project__title"]
