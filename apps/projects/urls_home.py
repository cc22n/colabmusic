"""Home URL — serves the homepage with dynamic context."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
]
