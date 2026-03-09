"""
Models for the rankings app.
Vote (Generic FK), RankingCache, ReputationLog.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.accounts.models import Genre, Role

User = get_user_model()


class Vote(models.Model):
    class VoteType(models.TextChoices):
        UPVOTE = "upvote", "Voto Positivo"
        DOWNVOTE = "downvote", "Voto Negativo"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Tipo de contenido votado (FinalMix, Lyrics, Beat, VocalTrack)",
    )
    object_id = models.PositiveBigIntegerField(
        db_index=True,
        help_text="ID del objeto votado",
    )
    content_object = GenericForeignKey("content_type", "object_id")
    vote_type = models.CharField(
        max_length=10,
        choices=VoteType.choices,
        default=VoteType.UPVOTE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Voto"
        verbose_name_plural = "Votos"
        unique_together = [("user", "content_type", "object_id")]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.vote_type} on {self.content_type.model} #{self.object_id}"


class RankingPeriod(models.TextChoices):
    WEEKLY = "weekly", "Semanal"
    MONTHLY = "monthly", "Mensual"
    ALL_TIME = "all_time", "Todo el Tiempo"


class RankingCache(models.Model):
    """Pre-calculated ranking data stored as JSON for fast retrieval."""

    ranking_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Tipo de ranking (global, by_role, by_genre, covers)",
    )
    period = models.CharField(
        max_length=20,
        choices=RankingPeriod.choices,
        default=RankingPeriod.WEEKLY,
        db_index=True,
    )
    genre = models.ForeignKey(
        Genre,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rankings",
        help_text="Filtro de género (null = todos los géneros)",
    )
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rankings",
        help_text="Filtro de rol (null = todos los roles)",
    )
    entries = models.JSONField(
        default=list,
        help_text="Entradas del ranking en formato JSON",
    )
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-calculated_at"]
        verbose_name = "Caché de Ranking"
        verbose_name_plural = "Cachés de Rankings"
        unique_together = [("ranking_type", "period", "genre", "role")]

    def __str__(self):
        return f"Ranking [{self.ranking_type}] — {self.period}"


class ReputationLog(models.Model):
    """Audit trail for reputation point changes."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reputation_logs",
    )
    points = models.IntegerField(help_text="Puntos ganados o perdidos (puede ser negativo)")
    reason = models.CharField(
        max_length=200,
        help_text="Motivo del cambio de puntuación",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log de Reputación"
        verbose_name_plural = "Logs de Reputación"

    def __str__(self):
        sign = "+" if self.points >= 0 else ""
        return f"{self.user.username}: {sign}{self.points} ({self.reason})"
