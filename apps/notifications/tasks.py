from celery import shared_task


@shared_task
def send_notification(
    recipient_id: int,
    notification_type: str,
    title: str,
    message: str,
    sender_id: int | None = None,
    link: str = "",
) -> None:
    """Create an in-app notification and optionally send an email."""
    pass


@shared_task
def send_email_notification(notification_id: int) -> None:
    """Send email for a given Notification instance."""
    pass


@shared_task
def cleanup_old_notifications(days: int = 90) -> None:
    """Delete read notifications older than `days` days."""
    pass
