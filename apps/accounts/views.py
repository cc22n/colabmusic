"""
Views for the accounts app.
ProfileDetailView: public profile page.
ProfileUpdateView: authenticated user's own settings page.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DetailView, UpdateView

from .forms import ProfileUpdateForm
from .models import UserProfile

User = get_user_model()


class ProfileDetailView(DetailView):
    """Public profile for any user, accessed via /accounts/profile/<username>/."""

    model = UserProfile
    template_name = "accounts/profile.html"
    context_object_name = "profile"

    def get_object(self, queryset=None):
        username = self.kwargs["username"]
        user = get_object_or_404(User, username=username)
        return get_object_or_404(UserProfile, user=user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = self.object
        ctx["is_own_profile"] = (
            self.request.user.is_authenticated
            and self.request.user == profile.user
        )
        # Projects the user has created (public only)
        # related_name on Project.created_by is "projects"
        public_projects_qs = profile.user.projects.filter(is_public=True)
        ctx["created_projects"] = public_projects_qs.order_by("-created_at")[:6]
        ctx["created_projects_count"] = public_projects_qs.count()
        # Badges earned
        ctx["badges"] = profile.user.badges.select_related("badge").order_by(
            "-awarded_at"
        )[:10]
        return ctx


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Edit the currently authenticated user's own profile — no <username> in URL."""

    model = UserProfile
    form_class = ProfileUpdateForm
    template_name = "accounts/settings.html"
    success_url = reverse_lazy("accounts:settings")

    def get_object(self, queryset=None):
        # Always returns the current user's profile — impossible to edit another user's.
        return get_object_or_404(UserProfile, user=self.request.user)
