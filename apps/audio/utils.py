"""
Audio processing utilities for ColabMusic.

All functions degrade gracefully if FFmpeg/FFprobe are not available:
- validate_mime_type: requires python-magic (always available)
- run_ffprobe:        returns partial metadata if ffprobe missing
- convert_to_mp3:    returns False if ffmpeg missing (caller marks FAILED)
- generate_waveform_peaks: returns [] if ffmpeg missing
"""

import json
import logging
import os
import shutil
import struct
import subprocess
import tempfile
from datetime import timedelta
from typing import Optional

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
    "audio/ogg",
    "audio/aac",
    "audio/mp4",
    "audio/x-m4a",
    "video/mp4",  # some AAC files report as video/mp4
}

MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
WAVEFORM_NUM_PEAKS = 800


# ---------------------------------------------------------------------------
# MIME type validation
# ---------------------------------------------------------------------------


def validate_mime_type(file_obj) -> str:
    """
    Read the first 2 KB of a file-like object and check MIME type with python-magic.
    Returns the MIME type string.
    Raises ValidationError if the type is not in ALLOWED_MIME_TYPES.
    """
    try:
        import magic as libmagic  # python-magic
    except ImportError:
        logger.warning("python-magic not installed — skipping MIME validation")
        return "application/octet-stream"

    header = file_obj.read(2048)
    file_obj.seek(0)
    mime = libmagic.from_buffer(header, mime=True)

    if mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"Tipo de archivo no permitido: {mime}. "
            "Usa MP3, WAV, FLAC, OGG o AAC."
        )
    return mime


def validate_file_size(file_obj, max_bytes: int = MAX_AUDIO_SIZE_BYTES) -> None:
    """Raise ValidationError if file exceeds max_bytes."""
    size = getattr(file_obj, "size", None)
    if size is None:
        # Seek to end to get size
        file_obj.seek(0, 2)
        size = file_obj.tell()
        file_obj.seek(0)
    if size > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValidationError(f"El archivo no puede superar {mb} MB.")


# ---------------------------------------------------------------------------
# FFprobe — metadata extraction
# ---------------------------------------------------------------------------


def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def run_ffprobe(file_path: str) -> dict:
    """
    Run ffprobe on file_path and return a metadata dict:
    {
        "duration_seconds": float,
        "bitrate_kbps": int,
        "sample_rate_hz": int,
        "codec": str,
    }
    Returns partial/empty dict if ffprobe is not available or fails.
    """
    if not _ffprobe_available():
        logger.warning("ffprobe not found — skipping metadata extraction")
        return {}

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error("ffprobe error: %s", result.stderr)
            return {}

        data = json.loads(result.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        audio = audio_streams[0] if audio_streams else {}

        duration_s = float(fmt.get("duration", 0) or audio.get("duration", 0) or 0)
        bitrate_bps = int(fmt.get("bit_rate", 0) or 0)
        sample_rate = int(audio.get("sample_rate", 0) or 0)
        codec = audio.get("codec_name", "")

        return {
            "duration_seconds": round(duration_s, 2),
            "bitrate_kbps": bitrate_bps // 1000 if bitrate_bps else 0,
            "sample_rate_hz": sample_rate,
            "codec": codec,
        }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        logger.error("ffprobe failed: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# FFmpeg — MP3 conversion
# ---------------------------------------------------------------------------


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def convert_to_mp3(input_path: str, output_path: str) -> bool:
    """
    Convert input audio to MP3 128kbps with loudnorm (-14 LUFS).
    Returns True on success, False if ffmpeg is unavailable or conversion fails.
    """
    if not _ffmpeg_available():
        logger.warning("ffmpeg not found — skipping MP3 conversion")
        return False

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-af", "loudnorm=I=-14:TP=-1:LRA=11",
        "-codec:a", "libmp3lame",
        "-b:a", "128k",
        "-ar", "44100",
        "-y",           # overwrite output
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,  # 2 minutes max
        )
        if result.returncode != 0:
            logger.error(
                "ffmpeg conversion failed (rc=%d): %s",
                result.returncode,
                result.stderr.decode(errors="replace")[:500],
            )
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.error("ffmpeg conversion error: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Waveform peak generation
# ---------------------------------------------------------------------------


def generate_waveform_peaks(
    file_path: str, num_peaks: int = WAVEFORM_NUM_PEAKS
) -> list:
    """
    Extract PCM data via FFmpeg and compute peak amplitudes.
    Returns a list of num_peaks floats in [0.0, 1.0].
    Returns [] if FFmpeg is not available or extraction fails.
    """
    if not _ffmpeg_available():
        logger.warning("ffmpeg not found — skipping waveform generation")
        return []

    # Extract mono 8kHz PCM s16le to stdout
    cmd = [
        "ffmpeg",
        "-i", file_path,
        "-ac", "1",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ar", "8000",
        "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0 or not result.stdout:
            logger.error("ffmpeg PCM extraction failed")
            return []

        raw = result.stdout
        num_samples = len(raw) // 2
        if num_samples == 0:
            return []

        samples = struct.unpack(f"<{num_samples}h", raw)
        chunk_size = max(1, num_samples // num_peaks)
        peaks = []
        for i in range(0, num_samples, chunk_size):
            chunk = samples[i : i + chunk_size]
            if chunk:
                peak = max(abs(s) for s in chunk) / 32768.0
                peaks.append(round(peak, 3))
            if len(peaks) >= num_peaks:
                break

        return peaks
    except (subprocess.TimeoutExpired, struct.error, OSError) as exc:
        logger.error("waveform generation error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Presigned URL helper
# ---------------------------------------------------------------------------


def get_streaming_url(file_field, request=None) -> Optional[str]:
    """
    Return the URL for an audio file field.
    - In DEBUG mode: returns the local media URL directly.
    - In production: generates a 1-hour presigned S3 URL.
    Returns None if the file field is empty.
    """
    from django.conf import settings

    if not file_field or not file_field.name:
        return None

    if settings.DEBUG:
        # Serve local file through Django's media server
        try:
            return file_field.url
        except Exception:
            return None

    # Production: presigned S3 URL
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        client = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": file_field.name,
            },
            ExpiresIn=3600,
        )
        return url
    except Exception as exc:
        logger.error("Failed to generate presigned URL: %s", exc)
        # Do NOT fall back to file_field.url — that would expose a direct S3 URL,
        # bypassing the private ACL on the bucket for files in private projects.
        return None
