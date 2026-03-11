"""
Celery tasks for the moderation app.
check_flag_threshold: triggered after each new Flag is created.
notify_moderators: sends in-app notifications to all staff users.
"""

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


@shared_task(bind=True, max_retries=3)
def check_flag_threshold(self, flag_id):
    """
    Triggered after a Flag is created.
    1. Count active (PENDING + REVIEWING) flags for the content.
    2. Update flag_count on the content object.
    3. If count >= MODERATION_AUTO_HIDE_THRESHOLD and not already hidden → auto-hide.
    4. If count >= MODERATION_NOTIFY_THRESHOLD → notify staff.
    """
    from apps.moderation.models import Flag, FlagStatus

    try:
        flag = Flag.objects.select_related("content_type").get(id=flag_id)
    except Flag.DoesNotExist:
        return  # Flag was deleted before task ran

    content_model = flag.content_type.model_class()
    if content_model is None:
        return

    try:
        content_obj = content_model.objects.get(id=flag.object_id)
    except content_model.DoesNotExist:
        return  # Content was deleted

    # Count active flags for this piece of content
    active_flags = Flag.objects.filter(
        content_type=flag.content_type,
        object_id=flag.object_id,
        status__in=[FlagStatus.PENDING, FlagStatus.REVIEWING],
    ).count()

    # Update denormalized counter
    if hasattr(content_obj, "flag_count"):
        content_obj.flag_count = active_flags
        content_obj.save(update_fields=["flag_count"])

    auto_hide_threshold = getattr(settings, "MODERATION_AUTO_HIDE_THRESHOLD", 3)
    notify_threshold = getattr(settings, "MODERATION_NOTIFY_THRESHOLD", 1)

    # Auto-hide if threshold reached and not already hidden
    if active_flags >= auto_hide_threshold and hasattr(content_obj, "is_hidden"):
        if not content_obj.is_hidden:
            content_obj.hide(
                reason=f"Auto-hidden: {active_flags} flags received"
            )

    # Notify staff when threshold is first crossed
    if active_flags >= notify_threshold:
        notify_moderators.delay(
            flag.content_type_id, flag.object_id, active_flags
        )


@shared_task
def notify_moderators(content_type_id, object_id, flag_count):
    """
    Creates in-app Notification for all staff/superuser accounts
    when flagged content reaches the notify threshold.
    """
    from apps.notifications.models import Notification

    try:
        ct = ContentType.objects.get(id=content_type_id)
    except ContentType.DoesNotExist:
        return

    model_name = ct.model
    staff_users = User.objects.filter(is_staff=True, is_active=True)

    notifications = [
        Notification(
            recipient=staff_user,
            notification_type="moderation_flag",
            title=f"Contenido reportado ({flag_count} reporte{'s' if flag_count != 1 else ''})",
            message=(
                f"El {model_name} #{object_id} ha recibido {flag_count} "
                f"reporte{'s' if flag_count != 1 else ''}. Revisa la cola de moderación."
            ),
            link=f"/moderation/queue/",
        )
        for staff_user in staff_users
    ]

    if notifications:
        Notification.objects.bulk_create(notifications, ignore_conflicts=True)
