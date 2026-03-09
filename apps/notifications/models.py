"""
Models for the notifications app.
Notification: in-app notifications for user events.
"""

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class NotificationType(models.TextChoices):
    VOTE_RECEIVED = "vote_received", "Voto Recibido"
    CONTRIBUTION_SELECTED = "contribution_selected", "Contribución Seleccionada"
    PROJECT_COMPLETE = "project_complete", "Proyecto Completado"
    NEW_CONTRIBUTION = "new_contribution", "Nueva Contribución"
    BADGE_AWARDED = "badge_awarded", "Insignia Obtenida"
    TOP_RANKING = "top_ranking", "Top en Rankings"
    MENTION = "mention", "Mención"


class Notification(models.Model):
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="Usuario que recibe la notificación",
    )
    sender = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_notifications",
        help_text="Usuario que generó la notificación (null para notificaciones del sistema)",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    link = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL relativa a la que lleva la notificación",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.notification_type}] → {self.recipient.username}: {self.title}"
