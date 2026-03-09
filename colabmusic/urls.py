"""
URL configuration for ColabMusic.
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("projects/", include("apps.projects.urls")),
    path("rankings/", include("apps.rankings.urls")),
    path("search/", include("apps.search.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("", include("apps.projects.urls_home")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
