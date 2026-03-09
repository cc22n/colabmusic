from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<slug:slug>/lyrics/submit/", views.submit_lyrics, name="submit-lyrics"),
    path("<slug:slug>/beats/submit/", views.submit_beat, name="submit-beat"),
    path("<slug:slug>/vocals/submit/", views.submit_vocal, name="submit-vocal"),
    path(
        "<slug:slug>/select/<str:contribution_type>/<int:pk>/",
        views.select_contribution,
        name="select",
    ),
]
