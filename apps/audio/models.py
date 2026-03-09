"""
Models for the audio app.
AudioProcessingTask tracks the async processing state of uploaded audio files.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

User = get_user_model()


class AudioProcessingTask(models.Model):
    """
    Tracks the Celery processing task for an uploaded audio file.
    Uses GenericFK to point at Beat, VocalTrack, or FinalMix instances.
    """

    class TaskStatus(models.TextChoices):
        QUEUED = "queued", "En Cola"
        RUNNING = "running", "Ejecutando"
        SUCCESS = "success", "Exitoso"
        FAILURE = "failure", "Fallido"
        RETRYING = "retrying", "Reintentando"

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Tipo de modelo de audio (Beat, VocalTrack, FinalMix)",
    )
    object_id = models.PositiveBigIntegerField(
        help_text="ID del objeto de audio",
    )
    audio_object = GenericForeignKey("content_type", "object_id")

    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="ID de la tarea Celery",
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.QUEUED,
        db_index=True,
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Mensaje de error si el procesamiento falló",
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Número de intentos de procesamiento",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tarea de Procesamiento"
        verbose_name_plural = "Tareas de Procesamiento"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Task [{self.status}] for {self.content_type.model} #{self.object_id}"
