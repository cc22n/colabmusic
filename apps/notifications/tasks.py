"""
Celery tasks for the notifications app.

send_notification      — persist in-app notification, trigger email if important.
send_email_notification — dispatch email for a saved Notification.
cleanup_old_notifications — delete read notifications older than N days.
"""

from celery import shared_task

# Notification types that trigger an email in addition to in-app notification
EMAIL_NOTIFICATION_TYPES = {
    "contribution_selected",
    "project_complete",
    "badge_awarded",
    "top_ranking",
}


@shared_task
def send_notification(
    recipient_id: int,
    notification_type: str,
    title: str,
    message: str,
    sender_id: int | None = None,
    link: str = "",
) -> int | None:
    """
    Create an in-app Notification for *recipient_id*.
    If the notification_type is in EMAIL_NOTIFICATION_TYPES, also
    dispatches send_email_notification as a follow-up task.

    Returns the created Notification pk, or None if recipient not found.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications.models import Notification

    User = get_user_model()

    try:
        recipient = User.objects.get(pk=recipient_id)
    except User.DoesNotExist:
        return None

    sender = None
    if sender_id is not None:
        try:
            sender = User.objects.get(pk=sender_id)
        except User.DoesNotExist:
            pass

    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link,
    )

    if notification_type in EMAIL_NOTIFICATION_TYPES:
        send_email_notification.delay(notification.pk)

    return notification.pk


@shared_task
def send_email_notification(notification_id: int) -> None:
    """
    Send a plain-text email for *notification_id*.
    Uses fail_silently=True so a broken SMTP config never crashes the queue.
    """
    from django.conf import settings
    from django.core.mail import send_mail

    from apps.notifications.models import Notification

    try:
        notification = Notification.objects.select_related("recipient").get(
            pk=notification_id
        )
    except Notification.DoesNotExist:
        return

    recipient_email = notification.recipient.email
    if not recipient_email:
        return

    send_mail(
        subject=f"[ColabMusic] {notification.title}",
        message=notification.message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@colabmusic.com"),
        recipient_list=[recipient_email],
        fail_silently=True,
    )


@shared_task
def cleanup_old_notifications(days: int = 90) -> int:
    """
    Delete read notifications older than *days* days.
    Returns the number of deleted rows.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.notifications.models import Notification

    cutoff = timezone.now() - timedelta(days=days)
    deleted_count, _ = Notification.objects.filter(
        is_read=True,
        created_at__lt=cutoff,
    ).delete()
    return deleted_count
