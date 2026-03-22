"""
Views for the notifications app.

NotificationListView  — full page list, marks all read on load.
unread_count          — HTMX: bell partial with current unread badge.
mark_read             — HTMX POST: mark a single notification read.
mark_all_read         — HTMX POST: mark all notifications read.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    """Full notification inbox — marks all unread as read on load."""

    model = Notification
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related(
            "sender"
        )
        # Mark all unread as read when the list page is viewed
        qs.filter(is_read=False).update(is_read=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Notificaciones"
        return ctx


def unread_count(request):
    """
    HTMX: returns the bell partial with the current unread count.
    Public endpoint — anonymous users always get count=0.
    """
    count = 0
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
    return render(
        request,
        "notifications/partials/bell.html",
        {"unread_count": count},
    )


@login_required
@require_POST
def mark_read(request, pk):
    """
    HTMX POST: mark a single notification as read.
    Returns an updated notification_item partial (is_read=True version).
    """
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    if request.headers.get("HX-Request"):
        return render(
            request,
            "notifications/partials/notification_item.html",
            {"notification": notification},
        )
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    """
    HTMX POST: mark every unread notification as read.
    Returns the updated bell partial (count=0).
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    if request.headers.get("HX-Request"):
        return render(
            request,
            "notifications/partials/bell.html",
            {"unread_count": 0},
        )
    return redirect("notifications:list")
