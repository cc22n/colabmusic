from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "notification_type", "title", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
    search_fields = ["recipient__username", "title"]
    readonly_fields = ["created_at"]
    actions = ["mark_as_read"]

    @admin.action(description="Marcar como leídas")
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
