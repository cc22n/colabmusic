"""
Tests for notifications views.
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification, NotificationType
from apps.notifications.tests.factories import NotificationFactory


class NotificationListViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.url = reverse("notifications:list")

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])

    def test_authenticated_returns_200(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_list_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "notifications/list.html")

    def test_shows_own_notifications(self):
        self.client.force_login(self.user)
        n = NotificationFactory(recipient=self.user, title="Mi notificación")
        response = self.client.get(self.url)
        self.assertContains(response, "Mi notificación")

    def test_does_not_show_other_users_notifications(self):
        self.client.force_login(self.user)
        other = UserFactory()
        NotificationFactory(recipient=other, title="Notificación ajena")
        response = self.client.get(self.url)
        self.assertNotContains(response, "Notificación ajena")

    def test_marks_unread_as_read_on_load(self):
        self.client.force_login(self.user)
        n = NotificationFactory(recipient=self.user, is_read=False)
        self.client.get(self.url)
        n.refresh_from_db()
        self.assertTrue(n.is_read)


class UnreadCountViewTest(TestCase):
    def setUp(self):
        self.url = reverse("notifications:unread-count")

    def test_anonymous_returns_200_with_zero(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_count_reflects_unread(self):
        user = UserFactory()
        self.client.force_login(user)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=True)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2")


class MarkReadViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.notification = NotificationFactory(recipient=self.user, is_read=False)
        self.url = reverse("notifications:mark-read", kwargs={"pk": self.notification.pk})

    def test_anonymous_redirects(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_marks_notification_read(self):
        self.client.force_login(self.user)
        self.client.post(self.url)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_returns_htmx_partial(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notifications/partials/notification_item.html")

    def test_other_users_notification_returns_404(self):
        self.client.force_login(self.user)
        other = UserFactory()
        n = NotificationFactory(recipient=other)
        url = reverse("notifications:mark-read", kwargs={"pk": n.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class MarkAllReadViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.url = reverse("notifications:mark-all-read")

    def test_anonymous_redirects(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_marks_all_unread_as_read(self):
        self.client.force_login(self.user)
        NotificationFactory(recipient=self.user, is_read=False)
        NotificationFactory(recipient=self.user, is_read=False)
        self.client.post(self.url)
        unread = Notification.objects.filter(recipient=self.user, is_read=False).count()
        self.assertEqual(unread, 0)

    def test_does_not_affect_other_users(self):
        self.client.force_login(self.user)
        other = UserFactory()
        n = NotificationFactory(recipient=other, is_read=False)
        self.client.post(self.url)
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_returns_bell_partial_for_htmx(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "notifications/partials/bell.html")
