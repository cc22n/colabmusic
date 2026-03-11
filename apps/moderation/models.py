"""
Models for the moderation app.
Flag: user report with Generic FK (same pattern as Vote).
ModerationAction: admin/moderator decision on a Flag.
ContentModerationMixin: abstract mixin for flaggable models.
VisibleManager: filters out hidden content.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

User = get_user_model()


# ── Manager ──────────────────────────────────────────────────────────────────


class VisibleManager(models.Manager):
    """Returns only non-hidden (moderation-approved) objects."""

    def get_queryset(self):
        return super().get_queryset().filter(is_hidden=False)


# ── Abstract mixin ────────────────────────────────────────────────────────────


class ContentModerationMixin(models.Model):
    """
    Add to FinalMix, Beat, VocalTrack, Lyrics.
    Provides is_hidden toggle, audit fields, and a denormalized flag counter.
    """

    is_hidden = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Oculto por moderación automática o manual",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_reason = models.CharField(max_length=200, blank=True, default="")
    flag_count = models.PositiveIntegerField(
        default=0,
        help_text="Contador denormalizado de flags activos",
    )

    class Meta:
        abstract = True

    def hide(self, reason="Auto-hidden: flag threshold reached"):
        self.is_hidden = True
        self.hidden_at = timezone.now()
        self.hidden_reason = reason
        self.save(update_fields=["is_hidden", "hidden_at", "hidden_reason"])

    def unhide(self):
        self.is_hidden = False
        self.hidden_at = None
        self.hidden_reason = ""
        self.save(update_fields=["is_hidden", "hidden_at", "hidden_reason"])


# ── Flag ──────────────────────────────────────────────────────────────────────


class FlagReason(models.TextChoices):
    COPYRIGHT = "copyright", "Infracción de derechos de autor"
    PLAGIARISM = "plagiarism", "Plagio de contenido"
    OFFENSIVE = "offensive", "Contenido ofensivo o inapropiado"
    SPAM = "spam", "Spam o contenido no relacionado"
    OTHER = "other", "Otro"


class FlagStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de revisión"
    REVIEWING = "reviewing", "En revisión"
    UPHELD = "upheld", "Reporte confirmado"
    DISMISSED = "dismissed", "Reporte descartado"


class Flag(models.Model):
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="flags_submitted",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    reason = models.CharField(max_length=20, choices=FlagReason.choices)
    description = models.TextField(
        max_length=500,
        blank=True,
        default="",
        help_text="Descripción opcional del problema",
    )
    status = models.CharField(
        max_length=20,
        choices=FlagStatus.choices,
        default=FlagStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reporte"
        verbose_name_plural = "Reportes"
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "content_type", "object_id"],
                name="unique_flag_per_user_per_content",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (
            f"Flag #{self.pk} — {self.get_reason_display()} "
            f"on {self.content_type.model} #{self.object_id}"
        )


# ── ModerationAction ──────────────────────────────────────────────────────────


class ActionType(models.TextChoices):
    REMOVE_CONTENT = "remove", "Contenido removido"
    HIDE_CONTENT = "hide", "Contenido oculto temporalmente"
    DISMISS = "dismiss", "Reporte descartado"
    WARN_USER = "warn", "Advertencia al usuario"
    BAN_USER = "ban", "Usuario suspendido"


class ModerationAction(models.Model):
    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, related_name="actions")
    moderator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="moderation_actions",
    )
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    notes = models.TextField(blank=True, default="", help_text="Notas internas del moderador")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Acción de Moderación"
        verbose_name_plural = "Acciones de Moderación"

    def __str__(self):
        return (
            f"{self.get_action_type_display()} by {self.moderator} on Flag #{self.flag_id}"
        )
