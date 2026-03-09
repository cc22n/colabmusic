"""
Models for the accounts app.
UserProfile, Role, Genre, Badge, UserBadge.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

User = get_user_model()


class Role(models.Model):
    class RoleName(models.TextChoices):
        LYRICIST = "lyricist", "Letrista"
        PRODUCER = "producer", "Productor"
        VOCALIST = "vocalist", "Vocalista"

    name = models.CharField(
        max_length=20,
        choices=RoleName.choices,
        unique=True,
        help_text="Rol musical del usuario",
    )
    display_name = models.CharField(max_length=50)
    description = models.TextField(blank=True, default="")
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Clase de ícono (ej. heroicons)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.display_name


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subgenres",
        help_text="Género padre (para sub-géneros)",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Género"
        verbose_name_plural = "Géneros"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("rankings:by-genre", kwargs={"genre": self.slug})


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=100, blank=True, default="")
    bio = models.TextField(blank=True, default="", help_text="Biografía del usuario")
    avatar = models.ImageField(
        upload_to="avatars/%Y/%m/",
        null=True,
        blank=True,
    )
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="users",
        help_text="Roles musicales del usuario",
    )
    genres = models.ManyToManyField(
        Genre,
        blank=True,
        related_name="users",
        help_text="Géneros musicales de interés",
    )
    reputation_score = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Puntuación de reputación acumulada",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reputation_score"]
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return self.display_name or self.user.username

    def get_absolute_url(self):
        return reverse("accounts:profile", kwargs={"username": self.user.username})


class Badge(models.Model):
    name = models.CharField(max_length=100, unique=True)
    condition = models.CharField(
        max_length=200,
        help_text="Condición para obtener la insignia",
    )
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name = "Insignia"
        verbose_name_plural = "Insignias"

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="badges",
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="user_badges",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-awarded_at"]
        verbose_name = "Insignia de Usuario"
        verbose_name_plural = "Insignias de Usuario"
        unique_together = [("user", "badge")]

    def __str__(self):
        return f"{self.user.username} — {self.badge.name}"
