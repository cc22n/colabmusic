"""
Celery tasks for the audio processing pipeline.

process_audio: main pipeline — validate MIME, extract metadata,
               convert to MP3, generate waveform, update model.
cleanup_failed_tasks: periodic maintenance task.
"""

import logging
import os
import tempfile
from datetime import timedelta

from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.core.files.base import File
from django.utils import timezone

from .models import AudioProcessingTask
from .utils import (
    convert_to_mp3,
    generate_waveform_peaks,
    run_ffprobe,
    validate_mime_type,
)

logger = logging.getLogger(__name__)

# Maps model_name string → (app_label, ModelClass)
AUDIO_MODELS = {
    "beat": ("projects", "Beat"),
    "vocaltrack": ("projects", "VocalTrack"),
    "finalmix": ("projects", "FinalMix"),
}


def _get_audio_model(model_name: str):
    """Return the model class for a given model_name string."""
    config = AUDIO_MODELS.get(model_name.lower())
    if config is None:
        raise ValueError(f"Unknown audio model: {model_name!r}")
    app_label, class_name = config
    return apps.get_model(app_label, class_name)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_audio(self, model_name: str, object_id: int) -> None:
    """
    Full audio processing pipeline for Beat, VocalTrack, or FinalMix.

    Steps:
    1. Fetch the object and set processing_status = PROCESSING
    2. Validate MIME type with python-magic
    3. Run FFprobe — extract duration, bitrate, sample_rate, codec
    4. Convert to MP3 128kbps (graceful fallback if FFmpeg unavailable)
    5. Generate waveform peaks JSON (graceful fallback)
    6. Save updated fields and set processing_status = READY

    On unrecoverable error: processing_status = FAILED (no retry).
    On transient error: retry up to 3 times.
    """
    Model = None
    obj = None

    try:
        Model = _get_audio_model(model_name)
        obj = Model.objects.get(pk=object_id)
    except (ValueError, Model.DoesNotExist if Model else Exception) as exc:
        logger.error("process_audio: cannot load %s #%s: %s", model_name, object_id, exc)
        return

    # Mark as processing
    obj.processing_status = "processing"
    obj.save(update_fields=["processing_status"])

    try:
        _run_pipeline(obj, model_name)
    except Exception as exc:
        logger.exception(
            "process_audio: pipeline failed for %s #%s: %s", model_name, object_id, exc
        )
        obj.processing_status = "failed"
        obj.save(update_fields=["processing_status"])

        # Retry for transient errors (not ValidationError / ValueError)
        from django.core.exceptions import ValidationError
        if not isinstance(exc, (ValidationError, ValueError)):
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                logger.error(
                    "process_audio: max retries exceeded for %s #%s", model_name, object_id
                )


def _run_pipeline(obj, model_name: str) -> None:
    """Execute the actual processing steps on the model instance."""
    from django.core.files.storage import default_storage

    if not obj.original_file or not obj.original_file.name:
        raise ValueError("No original_file to process")

    # ------------------------------------------------------------------
    # 1. Get local path of the original file
    # ------------------------------------------------------------------
    try:
        original_path = obj.original_file.path  # works for local storage
    except (NotImplementedError, AttributeError):
        # S3/remote storage: download to temp file
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(obj.original_file.name)[1]
        ) as tmp:
            tmp.write(obj.original_file.read())
            original_path = tmp.name
        _temp_original = original_path
    else:
        _temp_original = None

    try:
        _process_file(obj, original_path, model_name)
    finally:
        if _temp_original and os.path.exists(_temp_original):
            os.unlink(_temp_original)


def _process_file(obj, original_path: str, model_name: str) -> None:
    """Core processing given a local file path."""
    from django.core.exceptions import ValidationError

    # ------------------------------------------------------------------
    # 2. MIME validation (uses python-magic on the local file)
    # ------------------------------------------------------------------
    try:
        with open(original_path, "rb") as f:
            validate_mime_type(f)
    except ValidationError as exc:
        logger.warning("MIME validation failed for %s #%s: %s", model_name, obj.pk, exc)
        obj.processing_status = "failed"
        obj.save(update_fields=["processing_status"])
        return  # Don't retry MIME failures

    # ------------------------------------------------------------------
    # 3. FFprobe metadata
    # ------------------------------------------------------------------
    metadata = run_ffprobe(original_path)
    update_fields = []

    if metadata.get("duration_seconds"):
        obj.audio_duration = timedelta(seconds=metadata["duration_seconds"])
        update_fields.append("audio_duration")
    if metadata.get("bitrate_kbps"):
        obj.audio_bitrate = metadata["bitrate_kbps"]
        update_fields.append("audio_bitrate")
    if metadata.get("sample_rate_hz"):
        obj.audio_sample_rate = metadata["sample_rate_hz"]
        update_fields.append("audio_sample_rate")

    if update_fields:
        obj.save(update_fields=update_fields)

    # ------------------------------------------------------------------
    # 4. Convert to MP3 streaming file
    # ------------------------------------------------------------------
    converted = False
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
        tmp_mp3_path = tmp_mp3.name

    try:
        converted = convert_to_mp3(original_path, tmp_mp3_path)
        if converted and os.path.exists(tmp_mp3_path) and os.path.getsize(tmp_mp3_path) > 0:
            streaming_name = _build_streaming_name(obj, model_name)
            with open(tmp_mp3_path, "rb") as f:
                obj.streaming_file.save(streaming_name, File(f), save=False)
            logger.info("Saved streaming file for %s #%s", model_name, obj.pk)
        else:
            logger.warning(
                "FFmpeg conversion skipped/failed for %s #%s — using original",
                model_name, obj.pk,
            )
    finally:
        if os.path.exists(tmp_mp3_path):
            os.unlink(tmp_mp3_path)

    # ------------------------------------------------------------------
    # 5. Generate waveform peaks
    # ------------------------------------------------------------------
    peaks = generate_waveform_peaks(original_path)
    if peaks:
        obj.waveform_data = {"peaks": peaks}
    else:
        # Fallback: flat waveform so the player still renders
        obj.waveform_data = {"peaks": [0.5] * 100}
        logger.warning(
            "Waveform generation skipped for %s #%s — using placeholder",
            model_name, obj.pk,
        )

    # ------------------------------------------------------------------
    # 6. Mark as READY
    # ------------------------------------------------------------------
    obj.processing_status = "ready"
    obj.save(
        update_fields=["streaming_file", "waveform_data", "processing_status"]
    )
    logger.info("process_audio: READY %s #%s", model_name, obj.pk)


def _build_streaming_name(obj, model_name: str) -> str:
    """Build the S3/storage path for the MP3 streaming file."""
    project_id = getattr(obj, "project_id", "unknown")
    return f"audio/streaming/{model_name}/{project_id}/{obj.pk}.mp3"


@shared_task
def cleanup_failed_tasks() -> None:
    """Remove AudioProcessingTask records older than 7 days with FAILURE status."""
    cutoff = timezone.now() - timedelta(days=7)
    deleted, _ = AudioProcessingTask.objects.filter(
        status=AudioProcessingTask.TaskStatus.FAILURE,
        created_at__lt=cutoff,
    ).delete()
    logger.info("cleanup_failed_tasks: deleted %d old failure records", deleted)
