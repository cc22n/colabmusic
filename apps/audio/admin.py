from django.contrib import admin

from .models import AudioProcessingTask


@admin.register(AudioProcessingTask)
class AudioProcessingTaskAdmin(admin.ModelAdmin):
    list_display = ["__str__", "status", "celery_task_id", "attempts", "created_at"]
    list_filter = ["status", "content_type"]
    search_fields = ["celery_task_id", "error_message"]
    readonly_fields = ["created_at", "updated_at"]
