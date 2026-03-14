from django import forms
from allauth.account.forms import SignupForm

from .models import Genre, Role, UserProfile


# ── Signup ──────────────────────────────────────────────────────────────────────


class CustomSignupForm(SignupForm):
    """
    Extends allauth's SignupForm to let users choose their musical roles
    at registration time. Roles are saved by AccountAdapter.save_user().
    """

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        required=False,
        # We use a hidden widget — the actual UI is rendered as clickable
        # cards in the template using Alpine.js; this field just holds the
        # selected values that come back as multiple hidden inputs.
        # to_field_name='name' lets Alpine.js send "lyricist"/"producer"/
        # "vocalist" strings instead of integer PKs.
        widget=forms.MultipleHiddenInput,
        label="Roles musicales",
        to_field_name="name",
    )

    def save(self, request):
        # allauth calls save() → creates the User. Roles are set by the adapter.
        user = super().save(request)
        return user


# ── Profile edit ────────────────────────────────────────────────────────────────


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
