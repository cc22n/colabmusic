"""
Tests for apps.audio.views -- API endpoints.
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.projects.tests.factories import BeatFactory, ProjectFactory


class WaveformDataViewTest(TestCase):
    def test_returns_202_when_not_ready(self):
        beat = BeatFactory(processing_status="pending")
        url = reverse(
            "audio:waveform", kwargs={"model_name": "beat", "object_id": beat.pk}
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["status"], "pending")

    def test_returns_peaks_when_ready(self):
        beat = BeatFactory(
            processing_status="ready",
            waveform_data={"peaks": [0.1, 0.5, 0.9]},
        )
        url = reverse(
            "audio:waveform", kwargs={"model_name": "beat", "object_id": beat.pk}
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["peaks"], [0.1, 0.5, 0.9])

    def test_returns_400_for_unknown_model(self):
        url = "/api/waveform/unknownmodel/1/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_returns_404_for_nonexistent_object(self):
        url = reverse(
            "audio:waveform", kwargs={"model_name": "beat", "object_id": 99999}
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


class ProcessingStatusPollViewTest(TestCase):
    def test_returns_polling_html_when_pending(self):
        beat = BeatFactory(processing_status="pending")
        url = reverse(
            "audio:status", kwargs={"model_name": "beat", "object_id": beat.pk}
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"hx-get", resp.content)
        self.assertIn(b"cola", resp.content)

    def test_returns_polling_html_when_processing(self):
        beat = BeatFactory(processing_status="processing")
        url = reverse(
            "audio:status", kwargs={"model_name": "beat", "object_id": beat.pk}
        )
        resp = self.client.get(url)
        self.assertIn(b"Procesando", resp.content)

    def test_returns_player_html_when_ready(self):
        beat = BeatFactory(
            processing_status="ready",
            waveform_data={"peaks": [0.5]},
        )
        url = reverse(
            "audio:status", kwargs={"model_name": "beat", "object_id": beat.pk}
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"WaveSurfer", resp.content)
        self.assertIn(b"audio-player", resp.content)

    def test_returns_error_html_when_failed(self):
        beat = BeatFactory(processing_status="failed")
        url = reverse(
            "audio:status", kwargs={"model_name": "beat", "object_id": beat.pk}
        )
        resp = self.client.get(url)
        self.assertIn(b"Error", resp.content)


# ── Access control tests (IDOR fix) ───────────────────────────────────────────


class WaveformAccessControlTest(TestCase):
    """
    Verify that private project audio is inaccessible to non-owners,
    while public project audio remains accessible to everyone.
    """

    def setUp(self):
        self.owner = UserFactory()
        self.other = UserFactory()
        self.public_project = ProjectFactory(is_public=True, created_by=self.owner)
        self.private_project = ProjectFactory(is_public=False, created_by=self.owner)
        self.public_beat = BeatFactory(
            project=self.public_project, processing_status="ready",
            waveform_data={"peaks": [0.5]},
        )
        self.private_beat = BeatFactory(
            project=self.private_project, processing_status="ready",
            waveform_data={"peaks": [0.5]},
        )

    # ── waveform_data ──────────────────────────────────────────────────────────

    def test_waveform_public_project_allows_anonymous(self):
        """Anonymous users can access waveform data for public projects."""
        url = reverse(
            "audio:waveform",
            kwargs={"model_name": "beat", "object_id": self.public_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_waveform_private_project_denies_anonymous(self):
        """Anonymous users cannot access waveform data for private projects."""
        url = reverse(
            "audio:waveform",
            kwargs={"model_name": "beat", "object_id": self.private_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_waveform_private_project_denies_other_user(self):
        """Authenticated non-owner cannot access waveform data for private projects."""
        self.client.force_login(self.other)
        url = reverse(
            "audio:waveform",
            kwargs={"model_name": "beat", "object_id": self.private_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_waveform_private_project_allows_owner(self):
        """Project owner can access waveform data for their own private projects."""
        self.client.force_login(self.owner)
        url = reverse(
            "audio:waveform",
            kwargs={"model_name": "beat", "object_id": self.private_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    # ── processing_status_poll ─────────────────────────────────────────────────

    def test_status_poll_public_project_allows_anonymous(self):
        """Anonymous users can poll processing status for public project audio."""
        url = reverse(
            "audio:status",
            kwargs={"model_name": "beat", "object_id": self.public_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_status_poll_private_project_denies_anonymous(self):
        """Anonymous users cannot poll processing status for private project audio."""
        url = reverse(
            "audio:status",
            kwargs={"model_name": "beat", "object_id": self.private_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_status_poll_private_project_allows_owner(self):
        """Project owner can poll processing status for their private project audio."""
        self.client.force_login(self.owner)
        url = reverse(
            "audio:status",
            kwargs={"model_name": "beat", "object_id": self.private_beat.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
