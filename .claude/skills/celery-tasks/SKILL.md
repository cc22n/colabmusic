---
name: celery-tasks
description: "Celery task patterns for ColabMusic including audio processing, ranking calculation, and notifications. Use this skill when creating async tasks, scheduled jobs, or working with Celery configuration. Also use when the user mentions background tasks, queues, scheduled jobs, or async processing."
---

# Celery Tasks — ColabMusic

## Celery Configuration

```python
# colabmusic/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "colabmusic.settings.development")

app = Celery("colabmusic")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# settings/base.py
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 min soft limit
```

## Task Categories

### 1. Audio Processing Tasks (apps/audio/tasks.py)

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_audio(self, content_type_str, object_id):
    """Main audio processing pipeline."""
    try:
        # 1. Get the model instance
        # 2. Validate with FFprobe
        # 3. Extract metadata (duration, bitrate, sample_rate)
        # 4. Convert to MP3 128kbps
        # 5. Normalize volume (-14 LUFS)
        # 6. Generate waveform peaks
        # 7. Upload to S3
        # 8. Update model: processing_status = READY
    except Exception as exc:
        # Update model: processing_status = FAILED
        self.retry(exc=exc)
```

### 2. Ranking Calculation Tasks (apps/rankings/tasks.py)

```python
@shared_task
def calculate_trending_rankings():
    """Every 15 min — velocity of votes in last 72 hours."""

@shared_task
def calculate_weekly_rankings():
    """Every hour — top content by net votes this week."""

@shared_task
def calculate_monthly_rankings():
    """Every 6 hours — top content by net votes this month."""

@shared_task
def calculate_alltime_rankings():
    """Every 24 hours — all-time top content."""

@shared_task
def recalculate_user_reputation(user_id):
    """After each vote — update user's reputation score."""
```

### 3. Notification Tasks (apps/notifications/tasks.py)

```python
@shared_task
def notify_new_contribution(project_id, contribution_type, contributor_id):
    """Notify project creator when someone submits a contribution."""

@shared_task
def notify_selection(contribution_type, contribution_id):
    """Notify contributor when their work is selected."""

@shared_task
def send_email_notification(user_id, template_name, context):
    """Send email via django-anymail or SMTP."""
```

## Beat Schedule

```python
# celery.py
app.conf.beat_schedule = {
    "trending-rankings": {
        "task": "apps.rankings.tasks.calculate_trending_rankings",
        "schedule": crontab(minute="*/15"),
    },
    "weekly-rankings": {
        "task": "apps.rankings.tasks.calculate_weekly_rankings",
        "schedule": crontab(minute=0),  # Every hour
    },
    "monthly-rankings": {
        "task": "apps.rankings.tasks.calculate_monthly_rankings",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "alltime-rankings": {
        "task": "apps.rankings.tasks.calculate_alltime_rankings",
        "schedule": crontab(minute=0, hour=3),  # 3 AM daily
    },
}
```

## Task Conventions

- ALWAYS use `bind=True` for tasks that need retries
- ALWAYS pass serializable arguments (IDs, strings) — never model instances
- Set `max_retries=3` and `default_retry_delay=60` for IO tasks
- Use `self.retry(exc=exc)` in try/except blocks
- Log task start, success, and failure with structured logging
- Use `CELERY_TASK_TIME_LIMIT` to prevent runaway tasks
- Test tasks with `task.apply()` (synchronous) in unit tests

## Redis Cache Integration

```python
from django.core.cache import cache

# Cache ranking results
def get_trending():
    cached = cache.get("rankings:trending")
    if cached:
        return cached
    # Fallback to DB
    rankings = RankingCache.objects.filter(
        ranking_type="TRENDING"
    ).first()
    if rankings:
        cache.set("rankings:trending", rankings.entries, timeout=900)
    return rankings.entries if rankings else []
```
