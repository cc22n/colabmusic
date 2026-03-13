"""
Tests for apps.audio.tasks -- process_audio pipeline.
All FFmpeg and file operations are mocked.
"""

import io
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.audio.models import AudioProcessingTask
from apps.projects.tests.factories import BeatFactory, VocalTrackFactory


class ProcessAudioTaskTest(TestCase):
    """Tests for the process_audio Celery task."""

    def setUp(self):
        self.beat = BeatFactory(processing_status="pending")

    @patch("apps.audio.tasks.generate_waveform_peaks", return_value=[0.1, 0.5, 0.9])
    @patch("apps.audio.tasks.convert_to_mp3", return_value=False)
    @patch(
        "apps.audio.tasks.run_ffprobe",
        return_value={
            "duration_seconds": 120.0,
            "bitrate_kbps": 192,
            "sample_rate_hz": 44100,
            "codec": "mp3",
        },
    )
    @patch("apps.audio.tasks.validate_mime_type")
    def test_process_audio_success_saves_waveform(
        self, mock_mime, mock_probe, mock_convert, mock_waveform
    ):
        """Happy path: waveform saved, status set to ready."""
        from apps.audio.tasks import process_audio

        process_audio("beat", self.beat.pk)
        self.beat.refresh_from_db()
        self.assertEqual(self.beat.processing_status, "ready")
        self.assertIsNotNone(self.beat.waveform_data)
        self.assertIn("peaks", self.beat.waveform_data)
        self.assertEqual(self.beat.waveform_data["peaks"], [0.1, 0.5, 0.9])

    @patch("apps.audio.tasks.generate_waveform_peaks", return_value=[])
    @patch("apps.audio.tasks.convert_to_mp3", return_value=False)
    @patch("apps.audio.tasks.run_ffprobe", return_value={})
    @patch("apps.audio.tasks.validate_mime_type")
    def test_process_audio_ffmpeg_unavailable_uses_placeholder(
        self, mock_mime, mock_probe, mock_convert, mock_waveform
    ):
        """When FFmpeg is unavailable, status is still READY with placeholder waveform."""
        from apps.audio.tasks import process_audio

        process_audio("beat", self.beat.pk)
        self.beat.refresh_from_db()
        self.assertEqual(self.beat.processing_status, "ready")
        self.assertIsNotNone(self.beat.waveform_data)
        peaks = self.beat.waveform_data.get("peaks", [])
        self.assertGreater(len(peaks), 0)

    def test_process_audio_mime_failure_sets_failed(self):
        """MIME validation failure -> processing_status = failed."""
        from django.core.exceptions import ValidationError

        from apps.audio.tasks import process_audio

        with patch(
            "apps.audio.tasks._run_pipeline",
            side_effect=ValidationError("Tipo no permitido"),
        ):
            process_audio("beat", self.beat.pk)
        self.beat.refresh_from_db()
        self.assertEqual(self.beat.processing_status, "failed")

    def test_process_audio_unknown_model_does_not_raise(self):
        """Unknown model_name should log and return without raising."""
        from apps.audio.tasks import process_audio

        # Should not raise
        process_audio("unknownmodel", 99999)

    @patch("apps.audio.tasks.generate_waveform_peaks", return_value=[0.3])
    @patch("apps.audio.tasks.convert_to_mp3", return_value=False)
    @patch(
        "apps.audio.tasks.run_ffprobe",
        return_value={
            "duration_seconds": 60.0,
            "bitrate_kbps": 128,
            "sample_rate_hz": 44100,
            "codec": "wav",
        },
    )
    @patch("apps.audio.tasks.validate_mime_type")
    def test_process_audio_sets_metadata_fields(
        self, mock_mime, mock_probe, mock_convert, mock_waveform
    ):
        """Metadata from ffprobe is saved to the model."""
        from apps.audio.tasks import process_audio

        process_audio("beat", self.beat.pk)
        self.beat.refresh_from_db()
        self.assertEqual(self.beat.audio_bitrate, 128)
        self.assertEqual(self.beat.audio_sample_rate, 44100)
        self.assertIsNotNone(self.beat.audio_duration)

    @patch("apps.audio.tasks.generate_waveform_peaks", return_value=[0.2])
    @patch("apps.audio.tasks.convert_to_mp3", return_value=False)
    @patch("apps.audio.tasks.run_ffprobe", return_value={})
    @patch("apps.audio.tasks.validate_mime_type")
    def test_process_vocal_track(
        self, mock_mime, mock_probe, mock_convert, mock_waveform
    ):
        """process_audio also works for VocalTrack model."""
        vocal = VocalTrackFactory(processing_status="pending")
        from apps.audio.tasks import process_audio

        process_audio("vocaltrack", vocal.pk)
        vocal.refresh_from_db()
        self.assertEqual(vocal.processing_status, "ready")
