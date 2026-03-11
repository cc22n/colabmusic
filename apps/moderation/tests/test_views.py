"""
Tests for the moderation app views.
"""

from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.moderation.models import ActionType, Flag, FlagReason, FlagStatus, ModerationAction
from apps.projects.models import Lyrics
from apps.projects.tests.factories import LyricsFactory


def _lyrics_ct():
    return ContentType.objects.get_for_model(Lyrics)


class FlagFormViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.lyrics = LyricsFactory()
        self.url = reverse(
            "moderation:flag-form",
            kwargs={"content_type_str": "lyrics", "object_id": self.lyrics.pk},
        )

    def test_anonymous_user_redirected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/", resp["Location"])

    def test_authenticated_user_gets_form(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "moderation/flag_form.html")

    def test_unknown_content_type_returns_400(self):
        self.client.force_login(self.user)
        url = reverse(
            "moderation:flag-form",
            kwargs={"content_type_str": "unknown", "object_id": self.lyrics.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)


class SubmitFlagViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.lyrics = LyricsFactory()
        self.url = reverse(
            "moderation:submit-flag",
            kwargs={"content_type_str": "lyrics", "object_id": self.lyrics.pk},
        )

    def _post(self, user=None, data=None):
        user = user or self.user
        data = data or {"reason": FlagReason.SPAM, "description": "test spam"}
        self.client.force_login(user)
        return self.client.post(self.url, data)

    @patch("apps.moderation.views.check_flag_threshold.delay")
    def test_flag_created_on_valid_post(self, mock_task):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "moderation/flag_confirm.html")
        flag = Flag.objects.get(reporter=self.user, object_id=self.lyrics.pk)
        self.assertEqual(flag.reason, FlagReason.SPAM)
        self.assertEqual(flag.status, FlagStatus.PENDING)
        mock_task.assert_called_once_with(flag.id)

    @patch("apps.moderation.views.check_flag_threshold.delay")
    def test_duplicate_flag_returns_confirm_without_creating(self, mock_task):
        # Pre-create the flag directly to simulate a prior report
        ct = ContentType.objects.get_for_model(Lyrics)
        Flag.objects.create(
            reporter=self.user,
            content_type=ct,
            object_id=self.lyrics.pk,
            reason=FlagReason.SPAM,
        )
        initial_count = Flag.objects.count()
        # Posting again should not create a new flag
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Flag.objects.count(), initial_count)
        # Celery task should NOT have been called (duplicate caught before task)
        mock_task.assert_not_called()

    def test_anonymous_post_redirected(self):
        resp = self.client.post(self.url, {"reason": FlagReason.SPAM})
        self.assertEqual(resp.status_code, 302)


class AutoHideThresholdTest(TestCase):
    def setUp(self):
        self.lyrics = LyricsFactory()
        self.ct = _lyrics_ct()

    def _make_flag(self, user=None):
        user = user or UserFactory()
        return Flag.objects.create(
            reporter=user,
            content_type=self.ct,
            object_id=self.lyrics.pk,
            reason=FlagReason.SPAM,
        )

    def test_auto_hide_at_threshold(self):
        from apps.moderation.tasks import check_flag_threshold
        from django.test import override_settings

        with override_settings(MODERATION_AUTO_HIDE_THRESHOLD=3, MODERATION_NOTIFY_THRESHOLD=1):
            with patch("apps.moderation.tasks.notify_moderators.delay"):
                f1 = self._make_flag()
                check_flag_threshold(f1.id)
                self.lyrics.refresh_from_db()
                self.assertFalse(self.lyrics.is_hidden)

                f2 = self._make_flag()
                check_flag_threshold(f2.id)
                self.lyrics.refresh_from_db()
                self.assertFalse(self.lyrics.is_hidden)

                f3 = self._make_flag()
                check_flag_threshold(f3.id)
                self.lyrics.refresh_from_db()
                self.assertTrue(self.lyrics.is_hidden)

    def test_flag_count_updated_on_content(self):
        from apps.moderation.tasks import check_flag_threshold

        with patch("apps.moderation.tasks.notify_moderators.delay"):
            f1 = self._make_flag()
            check_flag_threshold(f1.id)
            self.lyrics.refresh_from_db()
            self.assertEqual(self.lyrics.flag_count, 1)


class ModerationQueueAccessTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.staff = UserFactory(is_staff=True)
        self.url = reverse("moderation:queue")

    def test_anonymous_redirected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_regular_user_forbidden(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_staff_can_access_queue(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "moderation/queue.html")


class ResolveFlagTest(TestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True)
        self.lyrics = LyricsFactory()
        ct = _lyrics_ct()
        self.flag = Flag.objects.create(
            reporter=UserFactory(),
            content_type=ct,
            object_id=self.lyrics.pk,
            reason=FlagReason.OFFENSIVE,
        )
        self.url = reverse("moderation:resolve-flag", kwargs={"flag_id": self.flag.pk})

    def _htmx_post(self, data):
        """POST with HTMX header so the view returns 200 instead of redirect."""
        return self.client.post(self.url, data, HTTP_HX_REQUEST="true")

    def test_uphold_hides_content(self):
        self.client.force_login(self.staff)
        resp = self._htmx_post({"action_type": ActionType.HIDE_CONTENT, "notes": ""})
        self.assertEqual(resp.status_code, 200)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, FlagStatus.UPHELD)
        self.lyrics.refresh_from_db()
        self.assertTrue(self.lyrics.is_hidden)
        self.assertEqual(ModerationAction.objects.filter(flag=self.flag).count(), 1)

    def test_dismiss_updates_flag_status(self):
        self.client.force_login(self.staff)
        resp = self._htmx_post({"action_type": ActionType.DISMISS, "notes": ""})
        self.assertEqual(resp.status_code, 200)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, FlagStatus.DISMISSED)

    def test_dismiss_unhides_auto_hidden_content(self):
        self.lyrics.hide(reason="Auto-hidden")
        self.client.force_login(self.staff)
        self._htmx_post({"action_type": ActionType.DISMISS, "notes": ""})
        self.lyrics.refresh_from_db()
        self.assertFalse(self.lyrics.is_hidden)

    def test_non_staff_cannot_resolve(self):
        self.client.force_login(UserFactory())
        resp = self.client.post(self.url, {"action_type": ActionType.DISMISS, "notes": ""})
        self.assertEqual(resp.status_code, 302)
