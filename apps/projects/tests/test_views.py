from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import (
    Lyrics,
    Project,
    ProjectStatus,
    ProjectType,
)
from apps.projects.tests.factories import (
    BeatFactory,
    LyricsFactory,
    ProjectFactory,
    VocalTrackFactory,
)


class ProjectListViewTest(TestCase):
    def setUp(self):
        self.url = reverse("projects:list")
        self.public_project = ProjectFactory(is_public=True, title="Proyecto Público")
        self.private_project = ProjectFactory(is_public=False, title="Proyecto Privado")

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/list.html")

    def test_only_public_projects_listed(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Proyecto Público")
        self.assertNotContains(resp, "Proyecto Privado")

    def test_htmx_returns_partial(self):
        resp = self.client.get(self.url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/partials/project_list.html")

    def test_filter_by_type(self):
        cover = ProjectFactory(is_public=True, project_type=ProjectType.COVER, title="Mi Cover")
        resp = self.client.get(self.url, {"type": "cover"})
        self.assertContains(resp, "Mi Cover")
        self.assertNotContains(resp, "Proyecto Público")

    def test_filter_by_query(self):
        resp = self.client.get(self.url, {"q": "Público"})
        self.assertContains(resp, "Proyecto Público")
        self.assertNotContains(resp, "Proyecto Privado")

    def test_archived_projects_excluded(self):
        archived = ProjectFactory(is_public=True, title="Archivado")
        archived.status = ProjectStatus.ARCHIVED
        archived.save()
        resp = self.client.get(self.url)
        self.assertNotContains(resp, "Archivado")


class ProjectDetailViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(is_public=True, created_by=self.user)
        self.url = reverse("projects:detail", kwargs={"slug": self.project.slug})

    def test_get_returns_200(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/detail.html")

    def test_private_project_not_visible_to_anon(self):
        private = ProjectFactory(is_public=False)
        resp = self.client.get(reverse("projects:detail", kwargs={"slug": private.slug}))
        self.assertEqual(resp.status_code, 404)

    def test_private_project_visible_to_owner(self):
        private = ProjectFactory(is_public=False, created_by=self.user)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("projects:detail", kwargs={"slug": private.slug}))
        self.assertEqual(resp.status_code, 200)

    def test_can_edit_flag_for_owner(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertTrue(resp.context["can_edit"])

    def test_can_edit_flag_false_for_others(self):
        other = UserFactory()
        self.client.force_login(other)
        resp = self.client.get(self.url)
        self.assertFalse(resp.context["can_edit"])


class ProjectCreateViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.url = reverse("projects:create")

    def test_anon_redirect_to_login(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/", resp["Location"])

    def test_get_returns_200_for_auth_user(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/form.html")

    def test_post_creates_original_project(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            "title": "Mi Nuevo Proyecto",
            "description": "Descripción test",
            "project_type": "original",
            "is_public": True,
            "allow_multiple_versions": False,
        })
        self.assertEqual(Project.objects.filter(title="Mi Nuevo Proyecto").count(), 1)
        project = Project.objects.get(title="Mi Nuevo Proyecto")
        self.assertEqual(project.created_by, self.user)
        self.assertEqual(project.status, ProjectStatus.SEEKING_LYRICS)
        self.assertRedirects(resp, reverse("projects:detail", kwargs={"slug": project.slug}))

    def test_post_creates_cover_with_seeking_beat_status(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {
            "title": "Mi Cover",
            "project_type": "cover",
            "is_public": True,
            "allow_multiple_versions": False,
        })
        project = Project.objects.get(title="Mi Cover")
        self.assertEqual(project.status, ProjectStatus.SEEKING_BEAT)


class ProjectUpdateViewTest(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.other = UserFactory()
        self.project = ProjectFactory(created_by=self.owner, is_public=True)
        self.url = reverse("projects:edit", kwargs={"slug": self.project.slug})

    def test_anon_redirect(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_non_owner_gets_403(self):
        self.client.force_login(self.other)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_owner_can_edit(self):
        self.client.force_login(self.owner)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_post_updates_title(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, {
            "title": "Título Actualizado",
            "project_type": self.project.project_type,
            "is_public": True,
            "allow_multiple_versions": False,
        })
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Título Actualizado")


class SubmitLyricsViewTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.project = ProjectFactory(
            is_public=True,
            project_type=ProjectType.ORIGINAL,
            status=ProjectStatus.SEEKING_LYRICS,
        )
        self.url = reverse("projects:submit-lyrics", kwargs={"slug": self.project.slug})

    def test_anon_redirect(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_htmx_get_returns_form_partial(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/partials/lyrics_form.html")

    def test_htmx_post_creates_lyrics(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {"content": "La la la...", "language": "es"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/partials/lyrics_item.html")
        self.assertEqual(Lyrics.objects.filter(project=self.project).count(), 1)

    def test_post_wrong_status_returns_400(self):
        self.project.status = ProjectStatus.SEEKING_BEAT
        self.project.save()
        self.client.force_login(self.user)
        resp = self.client.post(
            self.url,
            {"content": "test", "language": "es"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 400)


class SelectContributionViewTest(TestCase):
    def setUp(self):
        self.owner = UserFactory()
        self.other = UserFactory()
        self.project = ProjectFactory(
            created_by=self.owner,
            is_public=True,
            project_type=ProjectType.ORIGINAL,
            status=ProjectStatus.SEEKING_LYRICS,
        )
        self.lyrics = LyricsFactory(project=self.project, author=self.other)
        self.url = reverse(
            "projects:select",
            kwargs={
                "slug": self.project.slug,
                "contribution_type": "lyrics",
                "pk": self.lyrics.pk,
            },
        )

    def test_non_owner_gets_403(self):
        self.client.force_login(self.other)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_get_not_allowed(self):
        self.client.force_login(self.owner)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_owner_can_select_lyrics(self):
        self.client.force_login(self.owner)
        resp = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.lyrics.refresh_from_db()
        self.assertTrue(self.lyrics.is_selected)

    def test_select_advances_project_status(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.SEEKING_BEAT)

    def test_select_deselects_previous(self):
        other_lyrics = LyricsFactory(project=self.project, is_selected=True)
        self.client.force_login(self.owner)
        self.client.post(self.url, HTTP_HX_REQUEST="true")
        other_lyrics.refresh_from_db()
        self.assertFalse(other_lyrics.is_selected)


class SubmitBeatAudioValidationTest(TestCase):
    """Additional tests for audio validation in submit_beat."""

    def setUp(self):
        from apps.accounts.tests.factories import UserFactory
        from apps.projects.models import ProjectStatus
        from apps.projects.tests.factories import ProjectFactory

        self.user = UserFactory()
        self.project = ProjectFactory(
            status=ProjectStatus.SEEKING_BEAT,
            is_public=True,
        )
        self.url = reverse(
            "projects:submit-beat", kwargs={"slug": self.project.slug}
        )

    @patch("apps.audio.tasks.process_audio.delay")
    @patch("apps.projects.views.validate_mime_type")
    def test_submit_beat_dispatches_celery_task(self, mock_mime, mock_task):
        """A valid upload dispatches the process_audio Celery task."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_mime.return_value = "audio/mpeg"
        self.client.force_login(self.user)
        audio = SimpleUploadedFile("beat.mp3", b"fakemp3data", content_type="audio/mpeg")
        resp = self.client.post(
            self.url,
            {"original_file": audio, "bpm": 120, "key_signature": "Am"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        mock_task.assert_called_once()

    @patch("apps.projects.views.validate_mime_type")
    def test_submit_beat_rejects_invalid_mime(self, mock_mime):
        """Invalid MIME type adds error and returns 422."""
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_mime.side_effect = ValidationError("Tipo no permitido")
        self.client.force_login(self.user)
        audio = SimpleUploadedFile(
            "bad.exe", b"notaudio", content_type="application/octet-stream"
        )
        resp = self.client.post(
            self.url,
            {"original_file": audio},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 422)

    def test_submit_beat_rejects_oversized_file(self):
        """BeatSubmitForm validator rejects files over 50 MB."""
        from io import BytesIO

        from django.core.files.uploadedfile import InMemoryUploadedFile

        from apps.projects.forms import BeatSubmitForm

        # Create an UploadedFile where .size reports 60 MB (actual content is tiny)
        f = InMemoryUploadedFile(
            file=BytesIO(b"fake_audio"),
            field_name="original_file",
            name="big.mp3",
            content_type="audio/mpeg",
            size=60 * 1024 * 1024,
            charset=None,
        )
        form = BeatSubmitForm(data={"bpm": 120}, files={"original_file": f})
        self.assertFalse(form.is_valid())
        self.assertIn("original_file", form.errors)
