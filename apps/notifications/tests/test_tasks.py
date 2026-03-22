"""
Tests for notifications Celery tasks.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification, NotificationType
from apps.notifications.tasks import (
    cleanup_old_notifications,
    send_email_notification,
    send_notification,
)


class SendNotificationTaskTest(TestCase):
    def setUp(self):
        self.recipient = UserFactory()
        self.sender = UserFactory()

    def test_creates_notification(self):
        pk = send_notification(
            recipient_id=self.recipient.pk,
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Nuevo voto",
            message="Recibiste un upvote.",
            sender_id=self.sender.pk,
        )
        self.assertIsNotNone(pk)
        self.assertTrue(Notification.objects.filter(pk=pk).exists())

    def test_notification_fields_correct(self):
        pk = send_notification(
            recipient_id=self.recipient.pk,
            notification_type=NotificationType.CONTRIBUTION_SELECTED,
            title="Seleccionado",
            message="Tu beat fue elegido.",
            sender_id=self.sender.pk,
            link="/projects/mi-cancion/",
        )
        n = Notification.objects.get(pk=pk)
        self.assertEqual(n.recipient, self.recipient)
        self.assertEqual(n.sender, self.sender)
        self.assertEqual(n.notification_type, NotificationType.CONTRIBUTION_SELECTED)
        self.assertEqual(n.title, "Seleccionado")
        self.assertEqual(n.link, "/projects/mi-cancion/")
        self.assertFalse(n.is_read)

    def test_unknown_recipient_returns_none(self):
        result = send_notification(
            recipient_id=99999,
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Test",
            message="Test",
        )
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

    def test_no_sender_is_allowed(self):
        pk = send_notification(
            recipient_id=self.recipient.pk,
            notification_type=NotificationType.TOP_RANKING,
            title="Top 10",
            message="Estás en el top 10 semanal.",
        )
        n = Notification.objects.get(pk=pk)
        self.assertIsNone(n.sender)

    def test_invalid_sender_id_still_creates_notification(self):
        pk = send_notification(
            recipient_id=self.recipient.pk,
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Voto",
            message="Mensaje",
            sender_id=99999,
        )
        n = Notification.objects.get(pk=pk)
        self.assertIsNone(n.sender)


class SendEmailNotificationTaskTest(TestCase):
    def test_unknown_notification_id_does_not_raise(self):
        """Should silently return when notification not found."""
        send_email_notification(99999)  # Must not raise

    def test_recipient_with_no_email_does_not_raise(self):
        user = UserFactory(email="")
        n = Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.BADGE_AWARDED,
            title="Insignia",
            message="Obtuviste una insignia.",
        )
        send_email_notification(n.pk)  # Must not raise


class CleanupOldNotificationsTaskTest(TestCase):
    def test_deletes_old_read_notifications(self):
        user = UserFactory()
        old = Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Old",
            message="Old",
            is_read=True,
        )
        # Force created_at to 100 days ago
        Notification.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        deleted = cleanup_old_notifications(days=90)
        self.assertEqual(deleted, 1)
        self.assertFalse(Notification.objects.filter(pk=old.pk).exists())

    def test_keeps_unread_notifications(self):
        user = UserFactory()
        unread = Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Unread",
            message="Unread",
            is_read=False,
        )
        Notification.objects.filter(pk=unread.pk).update(
            created_at=timezone.now() - timedelta(days=100)
        )
        deleted = cleanup_old_notifications(days=90)
        self.assertEqual(deleted, 0)
        self.assertTrue(Notification.objects.filter(pk=unread.pk).exists())

    def test_keeps_recent_notifications(self):
        user = UserFactory()
        Notification.objects.create(
            recipient=user,
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Recent",
            message="Recent",
            is_read=True,
        )
        deleted = cleanup_old_notifications(days=90)
        self.assertEqual(deleted, 0)

    def test_returns_count_of_deleted(self):
        user = UserFactory()
        for _ in range(3):
            n = Notification.objects.create(
                recipient=user,
                notification_type=NotificationType.VOTE_RECEIVED,
                title="Old",
                message="Old",
                is_read=True,
            )
            Notification.objects.filter(pk=n.pk).update(
                created_at=timezone.now() - timedelta(days=100)
            )
        deleted = cleanup_old_notifications(days=90)
        self.assertEqual(deleted, 3)
