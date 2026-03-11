"""
Models for the projects app.
Project (state machine), Lyrics, Beat, VocalTrack, FinalMix + AudioMixin abstract.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.accounts.models import Genre
from apps.moderation.models import ContentModerationMixin, VisibleManager

User = get_user_model()


def audio_upload_path(instance, filename):
    """Upload path for original audio files."""
    app_label = instance.__class__.__name__.lower()
    return f"audio/original/{app_label}/{instance.pk}/{filename}"


def streaming_upload_path(instance, filename):
    """Upload path for streaming (MP3) audio files."""
    app_label = instance.__class__.__name__.lower()
    return f"audio/streaming/{app_label}/{instance.pk}/{filename}"


class ProcessingStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    PROCESSING = "processing", "Procesando"
    READY = "ready", "Listo"
    FAILED = "failed", "Error"


class AudioMixin(models.Model):
    """Abstract mixin for models that have an audio file."""

    original_file = models.FileField(
        upload_to=audio_upload_path,
        help_text="Archivo de audio original subido por el usuario",
    )
    streaming_file = models.FileField(
        upload_to=streaming_upload_path,
        blank=True,
        help_text="Archivo MP3 128kbps generado para streaming",
    )
    audio_format = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Formato del archivo original (mp3, wav, flac...)",
    )
    audio_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Duración del audio",
    )
    audio_bitrate = models.IntegerField(
        null=True,
        blank=True,
        help_text="Bitrate en kbps",
    )
    audio_sample_rate = models.IntegerField(
        null=True,
        blank=True,
        help_text="Sample rate en Hz",
    )
    file_size = models.BigIntegerField(
        default=0,
        help_text="Tamaño del archivo en bytes",
    )
    waveform_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Datos JSON de la forma de onda para Wavesurfer.js",
    )
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
        db_index=True,
        help_text="Estado del procesamiento async",
    )

    class Meta:
        abstract = True


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


class ProjectType(models.TextChoices):
    ORIGINAL = "original", "Original"
    COVER = "cover", "Cover"


class Project(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, max_length=220)
    description = models.TextField(blank=True, default="")
    project_type = models.CharField(
        max_length=10,
        choices=ProjectType.choices,
        default=ProjectType.ORIGINAL,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        db_index=True,
    )
    genre = models.ForeignKey(
        Genre,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projects",
    )
    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="projects",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    is_public = models.BooleanField(default=True, db_index=True)
    allow_multiple_versions = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        indexes = [
            models.Index(fields=["status", "project_type"]),
            models.Index(fields=["is_public", "status"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.status:
            if self.project_type == ProjectType.COVER:
                self.status = ProjectStatus.SEEKING_BEAT
            else:
                self.status = ProjectStatus.SEEKING_LYRICS
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"slug": self.slug})

    def transition_to(self, new_status: str) -> None:
        """Validate and apply a state machine transition."""
        allowed = VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValidationError(
                f"No se puede pasar de '{self.status}' a '{new_status}'."
            )
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Lyrics(ContentModerationMixin, models.Model):
    objects = models.Manager()
    visible = VisibleManager()
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="lyrics",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="lyrics",
    )
    content = models.TextField(help_text="Contenido de la letra")
    language = models.CharField(
        max_length=10,
        default="es",
        help_text="Código de idioma ISO 639-1",
    )
    is_selected = models.BooleanField(default=False, db_index=True)
    original_artist = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Artista original (solo para covers)",
    )
    original_song = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Canción original (solo para covers)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Letra"
        verbose_name_plural = "Letras"

    def __str__(self):
        return f"Letra de {self.author.username} para {self.project.title}"

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"slug": self.project.slug})


class Beat(ContentModerationMixin, AudioMixin, models.Model):
    objects = models.Manager()
    visible = VisibleManager()

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="beats",
    )
    producer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="beats",
    )
    bpm = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Beats por minuto",
    )
    key_signature = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Tonalidad (ej. C#m, Fmaj)",
    )
    description = models.TextField(blank=True, default="")
    is_selected = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Beat"
        verbose_name_plural = "Beats"

    def __str__(self):
        return f"Beat de {self.producer.username} para {self.project.title}"

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"slug": self.project.slug})


class VocalTrack(ContentModerationMixin, AudioMixin, models.Model):
    objects = models.Manager()
    visible = VisibleManager()

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="vocal_tracks",
    )
    vocalist = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="vocal_tracks",
    )
    description = models.TextField(blank=True, default="")
    is_selected = models.BooleanField(default=False, db_index=True)
    version_number = models.PositiveIntegerField(
        default=1,
        help_text="Número de versión de la pista vocal",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pista Vocal"
        verbose_name_plural = "Pistas Vocales"

    def __str__(self):
        return f"Vocal de {self.vocalist.username} para {self.project.title} (v{self.version_number})"

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"slug": self.project.slug})


class FinalMix(ContentModerationMixin, AudioMixin, models.Model):
    objects = models.Manager()
    visible = VisibleManager()

    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="final_mix",
    )
    lyrics = models.ForeignKey(
        Lyrics,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="final_mixes",
    )
    beat = models.ForeignKey(
        Beat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="final_mixes",
    )
    vocal_track = models.ForeignKey(
        VocalTrack,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="final_mixes",
    )
    cover_image = models.ImageField(
        upload_to="covers/%Y/%m/",
        null=True,
        blank=True,
        help_text="Imagen de portada del mix final",
    )
    play_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mix Final"
        verbose_name_plural = "Mixes Finales"

    def __str__(self):
        return f"Mix Final — {self.project.title}"

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"slug": self.project.slug})
