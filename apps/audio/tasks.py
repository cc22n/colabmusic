from celery import shared_task


@shared_task(bind=True, max_retries=3)
def process_audio(self, task_id: int) -> None:
    """
    Main audio processing pipeline:
    1. Validate MIME type with python-magic
    2. Run FFprobe to extract metadata
    3. Convert to MP3 128kbps via FFmpeg
    4. Generate waveform JSON (peaks)
    5. Upload both files to S3
    6. Mark AudioProcessingTask as SUCCESS
    """
    pass


@shared_task
def cleanup_failed_tasks() -> None:
    """Remove old failed processing tasks and temporary files."""
    pass
