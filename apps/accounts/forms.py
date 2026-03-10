from django import forms

from .models import Genre, Role, UserProfile


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating a user's profile settings."""

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Mis roles",
        help_text="Selecciona todos los roles que apliquen.",
    )
    genres = forms.ModelMultipleChoiceField(
        queryset=Genre.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Géneros de interés",
        help_text="Géneros musicales que más te interesan.",
    )

    class Meta:
        model = UserProfile
        fields = ["display_name", "bio", "avatar", "roles", "genres"]
        widgets = {
            "display_name": forms.TextInput(
                attrs={
                    "class": (
                        "w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 "
                        "text-white text-sm focus:outline-none focus:border-purple-500"
                    ),
                    "placeholder": "Tu nombre artístico",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": (
                        "w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 "
                        "text-white text-sm focus:outline-none focus:border-purple-500"
                    ),
                    "rows": 4,
                    "placeholder": "Cuéntanos sobre ti…",
                }
            ),
        }
        labels = {
            "display_name": "Nombre artístico",
            "bio": "Biografía",
            "avatar": "Foto de perfil",
        }
