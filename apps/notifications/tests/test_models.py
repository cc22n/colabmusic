from django.test import TestCase

from apps.notifications.models import Notification, NotificationType
from apps.notifications.tests.factories import NotificationFactory


class NotificationModelTest(TestCase):
    def test_create_notification(self):
        notification = NotificationFactory(
            title="Tu beat fue seleccionado",
            notification_type=NotificationType.CONTRIBUTION_SELECTED,
        )
        self.assertFalse(notification.is_read)
        self.assertIn(notification.recipient.username, str(notification))

    def test_notification_str(self):
        notification = NotificationFactory(
            notification_type=NotificationType.VOTE_RECEIVED,
            title="Nuevo voto",
        )
        self.assertIn("vote_received", str(notification))
        self.assertIn("Nuevo voto", str(notification))

    def test_notification_without_sender(self):
        notification = NotificationFactory(sender=None)
        self.assertIsNone(notification.sender)

    def test_default_is_unread(self):
        notification = NotificationFactory()
        self.assertFalse(notification.is_read)
