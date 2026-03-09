---
name: audio-pipeline
description: "Audio upload, processing, and streaming pipeline for ColabMusic. Use this skill when working on file uploads, audio conversion, waveform generation, FFmpeg integration, S3/MinIO storage, or the Wavesurfer.js player. Also use when the user mentions audio, uploads, streaming, waveforms, or media files."
---

# Audio Pipeline — ColabMusic

## Upload Flow

1. **Form submission** → Django `FileField` receives the file
2. **Validation** (synchronous in view):
   - Check file extension: `.mp3`, `.wav`, `.flac`, `.ogg`, `.aac`
   - Check MIME type with `python-magic` (NOT just extension)
   - Check file size: ≤50MB for beats/vocals, ≤100MB for final mixes
   - Rate limit: max 10 uploads/hour per user
3. **Save temp** → write to local temp dir or directly to model FileField
4. **Dispatch Celery task** → `process_audio.delay(model_name, object_id)`
5. **Return response** → HTMX partial showing "Processing..." status

## Celery Task: process_audio

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_audio(self, model_name, object_id):
    """
    1. Validate with FFprobe (get duration, bitrate, sample_rate, codec)
    2. Convert to MP3 128kbps for streaming (FFmpeg)
    3. Normalize volume to -14 LUFS (FFmpeg loudnorm filter)
    4. Generate waveform peaks (JSON array of ~800 float values)
    5. Upload original + streaming version to S3/MinIO
    6. Update model fields and set processing_status = READY
    """
```

## FFmpeg Commands

```bash
# Extract metadata
ffprobe -v quiet -print_format json -show_format -show_streams input.wav

# Convert to streaming MP3
ffmpeg -i input.wav -codec:a libmp3lame -b:a 128k -ar 44100 output.mp3

# Normalize volume
ffmpeg -i input.wav -af loudnorm=I=-14:TP=-1:LRA=11 -codec:a libmp3lame -b:a 128k output.mp3

# Generate waveform peaks (using audiowaveform or custom script)
audiowaveform -i input.mp3 --output-format json --pixels-per-second 10 -o waveform.json
```

## Waveform Data Format

Store as JSON array of normalized float values (0.0 to 1.0), approximately 800 points:

```json
{"peaks": [0.12, 0.34, 0.67, 0.89, 0.45, ...]}
```

If `audiowaveform` is not available, generate peaks with Python:

```python
import subprocess, json, struct

def generate_peaks(filepath, num_peaks=800):
    """Use FFmpeg to extract PCM data and calculate peaks."""
    cmd = [
        "ffmpeg", "-i", filepath, "-ac", "1", "-f", "s16le",
        "-acodec", "pcm_s16le", "-ar", "8000", "-"
    ]
    result = subprocess.run(cmd, capture_output=True)
    samples = struct.unpack(f"<{len(result.stdout)//2}h", result.stdout)
    chunk_size = max(1, len(samples) // num_peaks)
    peaks = []
    for i in range(0, len(samples), chunk_size):
        chunk = samples[i:i + chunk_size]
        peak = max(abs(s) for s in chunk) / 32768.0
        peaks.append(round(peak, 3))
    return peaks[:num_peaks]
```

## S3/MinIO Directory Structure

```
colab-music-bucket/
├── originals/
│   ├── beats/{project_id}/{beat_id}.{ext}
│   ├── vocals/{project_id}/{vocal_id}.{ext}
│   └── mixes/{project_id}/{mix_id}.{ext}
├── streaming/
│   ├── beats/{project_id}/{beat_id}.mp3
│   ├── vocals/{project_id}/{vocal_id}.mp3
│   └── mixes/{project_id}/{mix_id}.mp3
└── waveforms/
    └── {content_type}/{object_id}.json
```

## Django Storage Config

Use `django-storages` with S3Boto3Storage. Separate storage backends for originals vs streaming:

```python
# settings/base.py
STORAGES = {
    "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
AWS_STORAGE_BUCKET_NAME = env("S3_BUCKET_NAME", default="colab-music")
AWS_S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="http://localhost:9000")  # MinIO
```

## Security

- Generate presigned URLs for streaming (1-hour expiration)
- Set `Content-Disposition: attachment` on original files
- Validate MIME with python-magic BEFORE saving
- Run ClamAV scan if available (optional, non-blocking)
- Strip EXIF/metadata from uploaded files

## Wavesurfer.js Frontend

```javascript
const wavesurfer = WaveSurfer.create({
  container: '#waveform',
  waveColor: '#E94560',
  progressColor: '#0F3460',
  cursorColor: '#1A1A2E',
  barWidth: 2,
  barRadius: 3,
  responsive: true,
  height: 80,
  backend: 'MediaElement',  // Important: streams audio instead of loading all
});

// Load pre-computed peaks for instant waveform rendering
fetch(`/api/waveform/${trackId}/`)
  .then(r => r.json())
  .then(data => {
    wavesurfer.load(streamingUrl, data.peaks);
  });
```

## Dependencies

- `django-storages[boto3]` — S3 storage backend
- `python-magic` — MIME type detection
- `celery[redis]` — async task processing
- `ffmpeg` (system) — audio conversion
- `wavesurfer.js` (CDN) — frontend audio player
