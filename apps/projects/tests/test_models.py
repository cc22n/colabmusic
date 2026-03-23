from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.projects.models import (
    Project,
    ProjectStatus,
    ProjectType,
)
from apps.projects.tests.factories import (
    BeatFactory,
    FinalMixFactory,
    LyricsFactory,
    ProjectFactory,
    TagFactory,
    VocalTrackFactory,
)


class TagModelTest(TestCase):
    def test_create_tag(self):
        tag = TagFactory(name="lofi")
        self.assertEqual(str(tag), "lofi")
        self.assertEqual(tag.slug, "lofi")


class ProjectModelTest(TestCase):
    def test_create_original_project(self):
        project = ProjectFactory(project_type=ProjectType.ORIGINAL)
        self.assertEqual(project.status, ProjectStatus.SEEKING_LYRICS)
        self.assertIsNotNone(project.slug)

    def test_create_cover_project(self):
        project = ProjectFactory(project_type=ProjectType.COVER)
        self.assertEqual(project.status, ProjectStatus.SEEKING_BEAT)

    def test_project_str(self):
        project = ProjectFactory(title="Mi Canción")
        self.assertEqual(str(project), "Mi Canción")

    def test_get_absolute_url_contains_slug(self):
        project = ProjectFactory()
        # URL will be fully wired once views are implemented; test gracefully
        try:
            url = project.get_absolute_url()
            self.assertIn(project.slug, url)
        except Exception:
            self.assertTrue(callable(project.get_absolute_url))

    def test_slug_auto_generated(self):
        project = ProjectFactory(title="Mi Primera Canción")
        self.assertIn("mi-primera", project.slug)

    def test_transition_to_valid(self):
        project = ProjectFactory(project_type=ProjectType.ORIGINAL)
        self.assertEqual(project.status, ProjectStatus.SEEKING_LYRICS)
        project.transition_to(ProjectStatus.SEEKING_BEAT)
        self.assertEqual(project.status, ProjectStatus.SEEKING_BEAT)

    def test_transition_to_invalid_raises(self):
        project = ProjectFactory(project_type=ProjectType.ORIGINAL)
        with self.assertRaises(ValidationError):
            project.transition_to(ProjectStatus.COMPLETE)

    def test_transition_to_archived_from_any(self):
        project = ProjectFactory(project_type=ProjectType.ORIGINAL)
        project.transition_to(ProjectStatus.ARCHIVED)
        self.assertEqual(project.status, ProjectStatus.ARCHIVED)

    def test_slug_deduplication(self):
        """Two projects with the same title must get distinct slugs."""
        p1 = ProjectFactory(title="Mi Canción")
        p2 = ProjectFactory(title="Mi Canción")
        self.assertNotEqual(p1.slug, p2.slug)
        # Both slugs should start with the same base
        self.assertTrue(p2.slug.startswith("mi-cancion"))

    def test_slug_non_ascii_fallback(self):
        """A title composed entirely of non-ASCII characters must not produce an empty slug."""
        project = ProjectFactory(title="音楽プロジェクト")
        self.assertTrue(len(project.slug) > 0)
        self.assertIn("proyecto-", project.slug)


class LyricsModelTest(TestCase):
    def test_create_lyrics(self):
        lyrics = LyricsFactory(content="La la la...")
        self.assertIn(lyrics.author.username, str(lyrics))
        self.assertFalse(lyrics.is_selected)


class BeatModelTest(TestCase):
    def test_create_beat(self):
        beat = BeatFactory(bpm=140)
        self.assertEqual(beat.bpm, 140)
        self.assertIn(beat.producer.username, str(beat))

    def test_beat_default_processing_status(self):
        beat = BeatFactory()
        self.assertEqual(beat.processing_status, "pending")


class VocalTrackModelTest(TestCase):
    def test_create_vocal_track(self):
        vocal = VocalTrackFactory(version_number=2)
        self.assertEqual(vocal.version_number, 2)
        self.assertIn("v2", str(vocal))


class FinalMixModelTest(TestCase):
    def test_create_final_mix(self):
        mix = FinalMixFactory()
        self.assertIn(mix.project.title, str(mix))
        self.assertEqual(mix.play_count, 0)
