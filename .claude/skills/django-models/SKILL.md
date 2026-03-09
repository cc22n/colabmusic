---
name: django-models
description: "Django model patterns and conventions for ColabMusic. Use this skill when creating, modifying, or reviewing any Django model, migration, or database schema. Also use when the user mentions models, fields, relationships, or database design."
---

# Django Models — ColabMusic Conventions

## Model Base Pattern

Every model in this project MUST follow this pattern:

```python
from django.db import models
from django.urls import reverse


class MyModel(models.Model):
    # Fields here...
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "My Model"
        verbose_name_plural = "My Models"

    def __str__(self):
        return self.title  # Always return something meaningful

    def get_absolute_url(self):
        return reverse("app:model-detail", kwargs={"slug": self.slug})
```

## Field Conventions

- Use `SlugField(unique=True)` for URL-friendly identifiers, auto-populated via `django.utils.text.slugify` in `save()`
- Use `CharField(choices=...)` for finite state fields with a corresponding TextChoices class
- Use `ManyToManyField` for roles and genres (users can have multiple)
- Use `GenericForeignKey` only for the Vote model
- Always set `help_text` on non-obvious fields
- Always set `blank=True, null=True` together for optional fields (except CharField where use `blank=True, default=""`)
- ImageField and FileField: always specify `upload_to` with a callable or pattern

## State Machine (Project.status)

```python
class ProjectStatus(models.TextChoices):
    SEEKING_LYRICS = "seeking_lyrics", "Buscando Letrista"
    SEEKING_BEAT = "seeking_beat", "Buscando Productor"
    SEEKING_VOCALS = "seeking_vocals", "Buscando Vocalista"
    IN_REVIEW = "in_review", "En Revisión"
    COMPLETE = "complete", "Completa"
    ARCHIVED = "archived", "Archivada"

VALID_TRANSITIONS = {
    ProjectStatus.SEEKING_LYRICS: [ProjectStatus.SEEKING_BEAT, ProjectStatus.ARCHIVED],
    ProjectStatus.SEEKING_BEAT: [ProjectStatus.SEEKING_VOCALS, ProjectStatus.ARCHIVED],
    ProjectStatus.SEEKING_VOCALS: [ProjectStatus.IN_REVIEW, ProjectStatus.ARCHIVED],
    ProjectStatus.IN_REVIEW: [ProjectStatus.COMPLETE, ProjectStatus.ARCHIVED],
    ProjectStatus.COMPLETE: [ProjectStatus.ARCHIVED],
    ProjectStatus.ARCHIVED: [],
}
```

Implement `transition_to(new_status)` method on Project that validates transitions.

## AudioMixin (Abstract Base)

Beat, VocalTrack, and FinalMix share audio fields via this abstract model:

```python
class AudioMixin(models.Model):
    original_file = models.FileField(upload_to=audio_upload_path)
    streaming_file = models.FileField(upload_to=streaming_upload_path, blank=True)
    audio_format = models.CharField(max_length=10)
    audio_duration = models.DurationField(null=True, blank=True)
    audio_bitrate = models.IntegerField(null=True, blank=True)
    audio_sample_rate = models.IntegerField(null=True, blank=True)
    file_size = models.BigIntegerField(default=0)
    waveform_data = models.JSONField(null=True, blank=True)
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )

    class Meta:
        abstract = True
```

## Indexes

Add `db_index=True` to fields commonly used in filters: `status`, `project_type`, `is_selected`, `processing_status`. Add compound indexes for common query patterns via `Meta.indexes`.

## Signals

- Use signals sparingly — prefer overriding `save()` or using model methods
- Exception: `post_save` on User to auto-create UserProfile
- Audio processing: trigger Celery task in the view after successful save, NOT in a signal

## Factories (for testing)

Every model MUST have a factory in `apps/<app>/tests/factories.py`:

```python
import factory
from apps.accounts.models import UserProfile

class UserProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserProfile
    
    user = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    display_name = factory.Faker("user_name")
    bio = factory.Faker("text", max_nb_chars=200)
```
