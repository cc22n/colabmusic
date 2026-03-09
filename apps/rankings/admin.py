from django.contrib import admin

from .models import RankingCache, ReputationLog, Vote


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["user", "vote_type", "content_type", "object_id", "created_at"]
    list_filter = ["vote_type", "content_type"]
    search_fields = ["user__username"]
    readonly_fields = ["created_at"]


@admin.register(RankingCache)
class RankingCacheAdmin(admin.ModelAdmin):
    list_display = ["ranking_type", "period", "genre", "role", "calculated_at"]
    list_filter = ["ranking_type", "period"]
    readonly_fields = ["calculated_at"]


@admin.register(ReputationLog)
class ReputationLogAdmin(admin.ModelAdmin):
    list_display = ["user", "points", "reason", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "reason"]
    readonly_fields = ["created_at"]
