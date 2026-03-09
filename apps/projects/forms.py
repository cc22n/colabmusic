import os

from django import forms
from django.core.exceptions import ValidationError

from .models import Beat, FinalMix, Lyrics, Project, Tag, VocalTrack

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"}


def validate_audio_extension(file):
    """Validate that the uploaded file has an allowed audio extension."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValidationError(
            f"Formato no permitido '{ext}'. "
            f"Usa: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"
        )


class ProjectForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "lofi, trap, acústico...",
                "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
            }
        ),
        help_text="Etiquetas separadas por coma",
    )

    class Meta:
        model = Project
        fields = [
            "title",
            "description",
            "project_type",
            "genre",
            "is_public",
            "allow_multiple_versions",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "placeholder": "Nombre del proyecto...",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "rows": 4,
                    "placeholder": "Describe tu proyecto...",
                }
            ),
            "project_type": forms.Select(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500",
                }
            ),
            "genre": forms.Select(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500",
                }
            ),
            "is_public": forms.CheckboxInput(
                attrs={"class": "rounded bg-gray-800 border-gray-700 text-purple-500"}
            ),
            "allow_multiple_versions": forms.CheckboxInput(
                attrs={"class": "rounded bg-gray-800 border-gray-700 text-purple-500"}
            ),
        }

    def save(self, commit=True):
        project = super().save(commit=commit)
        if commit:
            self._save_tags(project)
        return project

    def _save_tags(self, project):
        raw = self.cleaned_data.get("tags", "")
        project.tags.clear()
        for name in [t.strip().lower() for t in raw.split(",") if t.strip()]:
            tag, _ = Tag.objects.get_or_create(name=name)
            project.tags.add(tag)


class LyricsForm(forms.ModelForm):
    class Meta:
        model = Lyrics
        fields = ["content", "language", "original_artist", "original_song"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 font-mono",
                    "rows": 10,
                    "placeholder": "Escribe la letra aquí...",
                }
            ),
            "language": forms.Select(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500",
                }
            ),
            "original_artist": forms.TextInput(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "placeholder": "Artista original (solo covers)...",
                }
            ),
            "original_song": forms.TextInput(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "placeholder": "Nombre de la canción original...",
                }
            ),
        }

    LANGUAGE_CHOICES = [
        ("es", "Español"),
        ("en", "Inglés"),
        ("pt", "Portugués"),
        ("fr", "Francés"),
        ("it", "Italiano"),
        ("de", "Alemán"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"].widget = forms.Select(
            choices=self.LANGUAGE_CHOICES,
            attrs={
                "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500",
            },
        )
        self.fields["original_artist"].required = False
        self.fields["original_song"].required = False


class BeatSubmitForm(forms.ModelForm):
    original_file = forms.FileField(
        validators=[validate_audio_extension],
        widget=forms.FileInput(
            attrs={
                "class": "block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-700",
                "accept": ",".join(ALLOWED_AUDIO_EXTENSIONS),
            }
        ),
        help_text="Formatos: MP3, WAV, FLAC, AAC, OGG",
    )

    class Meta:
        model = Beat
        fields = ["original_file", "description", "bpm", "key_signature"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "rows": 3,
                    "placeholder": "Describe tu beat (estilo, vibe, influencias)...",
                }
            ),
            "bpm": forms.NumberInput(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "placeholder": "120",
                    "min": 40,
                    "max": 300,
                }
            ),
            "key_signature": forms.TextInput(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "placeholder": "Cm, Fmaj, A#...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bpm"].required = False
        self.fields["key_signature"].required = False
        self.fields["description"].required = False


class VocalSubmitForm(forms.ModelForm):
    original_file = forms.FileField(
        validators=[validate_audio_extension],
        widget=forms.FileInput(
            attrs={
                "class": "block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-700",
                "accept": ",".join(ALLOWED_AUDIO_EXTENSIONS),
            }
        ),
        help_text="Formatos: MP3, WAV, FLAC, AAC, OGG",
    )

    class Meta:
        model = VocalTrack
        fields = ["original_file", "description", "version_number"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500",
                    "rows": 3,
                    "placeholder": "Notas sobre la grabación...",
                }
            ),
            "version_number": forms.NumberInput(
                attrs={
                    "class": "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-purple-500",
                    "min": 1,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
