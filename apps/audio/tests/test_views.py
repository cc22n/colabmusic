"""
Tests for apps.audio.views -- API endpoints.
"""

from django.test import TestCase
from django.urls import reverse

from apps.projects.tests.factories import BeatFactory


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
