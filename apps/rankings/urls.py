from django.urls import path

from . import views

app_name = "rankings"

urlpatterns = [
    path("", views.RankingsView.as_view(), name="global"),
    path("trending/", views.TrendingView.as_view(), name="trending"),
    path("by-genre/<slug:genre>/", views.RankingByGenreView.as_view(), name="by-genre"),
    path(
        "vote/<str:content_type_str>/<int:object_id>/",
        views.cast_vote,
        name="cast-vote",
    ),
    # path("by-role/<str:role>/", views.RankingByRoleView.as_view(), name="by-role"),
    # path("covers/", views.CoverRankingsView.as_view(), name="covers"),
]
