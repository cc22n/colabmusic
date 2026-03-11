from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    # User-facing: get the flag form modal (HTMX GET)
    path(
        "flag/<str:content_type_str>/<int:object_id>/",
        views.flag_form,
        name="flag-form",
    ),
    # User-facing: submit a flag (HTMX POST)
    path(
        "flag/<str:content_type_str>/<int:object_id>/submit/",
        views.submit_flag,
        name="submit-flag",
    ),
    # Staff moderation queue
    path("queue/", views.moderation_queue, name="queue"),
    # Staff resolve action
    path("resolve/<int:flag_id>/", views.resolve_flag, name="resolve-flag"),
]
