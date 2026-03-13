from django.urls import path

from . import views

app_name = "audio"

urlpatterns = [
    # GET /api/waveform/<model_name>/<object_id>/
    # Returns JSON with peaks, streaming_url and duration
    path(
        "waveform/<str:model_name>/<int:object_id>/",
        views.waveform_data,
        name="waveform",
    ),
    # GET /api/audio/status/<model_name>/<object_id>/
    # HTMX polling — returns HTML status badge or full player when ready
    path(
        "audio/status/<str:model_name>/<int:object_id>/",
        views.processing_status_poll,
        name="status",
    ),
]
