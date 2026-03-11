"""
Tests for the moderation app models.
Covers: Flag creation, duplicate constraint, ContentModerationMixin hide/unhide,
VisibleManager filtering.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.moderation.models import Flag, FlagReason, FlagStatus
from apps.projects.models import Beat, Lyrics
from apps.projects.tests.factories import BeatFactory, LyricsFactory


class FlagModelTest(TestCase):
    def setUp(self):
        self.reporter = UserFactory()
        self.lyrics = LyricsFactory()
        self.ct = ContentType.objects.get_for_model(Lyrics)

    def _create_flag(self, reporter=None, obj=None, reason=FlagReason.SPAM):
        reporter = reporter or self.reporter
        obj = obj or self.lyrics
        ct = ContentType.objects.get_for_model(type(obj))
        return Flag.objects.create(
            reporter=reporter,
            content_type=ct,
            object_id=obj.pk,
            reason=reason,
        )

    # 1. Flag can be created successfully
    def test_flag_creation(self):
        flag = self._create_flag()
        self.assertEqual(flag.status, FlagStatus.PENDING)
        self.assertEqual(flag.reporter, self.reporter)
        self.assertEqual(flag.object_id, self.lyrics.pk)
        self.assertEqual(flag.content_type, self.ct)

    # 2. Duplicate flag (same user + same content) is rejected
    def test_duplicate_flag_raises_integrity_error(self):
        self._create_flag()
        with self.assertRaises(IntegrityError):
            self._create_flag()  # same reporter + same content

    # 3. Different users can flag the same content
    def test_multiple_users_can_flag_same_content(self):
        user2 = UserFactory()
        flag1 = self._create_flag()
        flag2 = self._create_flag(reporter=user2)
        self.assertNotEqual(flag1.pk, flag2.pk)
        self.assertEqual(Flag.objects.filter(object_id=self.lyrics.pk).count(), 2)

    # 4. __str__ returns meaningful representation
    def test_flag_str(self):
        flag = self._create_flag()
        self.assertIn("Flag #", str(flag))
        self.assertIn("lyrics", str(flag))


class ContentModerationMixinTest(TestCase):
    def setUp(self):
        self.lyrics = LyricsFactory()

    # 5. hide() sets is_hidden=True and records hidden_at
    def test_hide_sets_fields(self):
        before = timezone.now()
        self.lyrics.hide(reason="Test hide")
        self.lyrics.refresh_from_db()
        self.assertTrue(self.lyrics.is_hidden)
        self.assertEqual(self.lyrics.hidden_reason, "Test hide")
        self.assertIsNotNone(self.lyrics.hidden_at)
        self.assertGreaterEqual(self.lyrics.hidden_at, before)

    # 6. unhide() clears is_hidden and resets fields
    def test_unhide_clears_fields(self):
        self.lyrics.hide(reason="hide")
        self.lyrics.unhide()
        self.lyrics.refresh_from_db()
        self.assertFalse(self.lyrics.is_hidden)
        self.assertIsNone(self.lyrics.hidden_at)
        self.assertEqual(self.lyrics.hidden_reason, "")


class VisibleManagerTest(TestCase):
    def setUp(self):
        self.visible_lyrics = LyricsFactory()
        self.hidden_lyrics = LyricsFactory()
        self.hidden_lyrics.hide(reason="Moderaci\u00f3n")

    # 7. visible manager excludes hidden content
    def test_visible_manager_excludes_hidden(self):
        visible_pks = list(Lyrics.visible.values_list("pk", flat=True))
        self.assertIn(self.visible_lyrics.pk, visible_pks)
        self.assertNotIn(self.hidden_lyrics.pk, visible_pks)

    # 8. objects manager returns all content including hidden
    def test_objects_manager_includes_hidden(self):
        all_pks = list(Lyrics.objects.values_list("pk", flat=True))
        self.assertIn(self.visible_lyrics.pk, all_pks)
        self.assertIn(self.hidden_lyrics.pk, all_pks)

    # 9. Beat model also uses VisibleManager correctly
    def test_visible_manager_on_beat(self):
        visible_beat = BeatFactory()
        hidden_beat = BeatFactory()
        hidden_beat.hide(reason="Auto-hidden")

        beat_pks = list(Beat.visible.values_list("pk", flat=True))
        self.assertIn(visible_beat.pk, beat_pks)
        self.assertNotIn(hidden_beat.pk, beat_pks)
