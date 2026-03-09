from celery import shared_task


@shared_task
def process_audio_file(audio_model: str, object_id: int) -> None:
    """
    Process an uploaded audio file:
    1. Validate with FFprobe
    2. Extract metadata (duration, bitrate, format)
    3. Convert to MP3 128kbps for streaming
    4. Generate waveform JSON
    5. Upload to S3
    6. Update model processing_status = READY
    """
    pass


@shared_task
def generate_waveform(audio_model: str, object_id: int) -> None:
    """Generate waveform JSON data for Wavesurfer.js."""
    pass


@shared_task
def finalize_project(project_id: int) -> None:
    """Transition a project to COMPLETE status after final mix is created."""
    pass
