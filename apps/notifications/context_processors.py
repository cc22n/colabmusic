"""
Context processors for the notifications app.
Injects unread_notification_count into every template context.
"""


def unread_notification_count(request):
    """Add unread notification count for the authenticated user."""
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0}
    count = request.user.notifications.filter(is_read=False).count()
    return {"unread_notification_count": count}
