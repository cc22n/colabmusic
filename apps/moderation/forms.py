from django import forms

from .models import ActionType, FlagReason


class FlagForm(forms.Form):
    """Form for submitting a content report."""

    reason = forms.ChoiceField(
        choices=FlagReason.choices,
        widget=forms.RadioSelect,
        label="Motivo del reporte",
    )
    description = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Describe el problema (opcional)...",
                "class": (
                    "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 "
                    "text-white text-sm placeholder-gray-500 "
                    "focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                ),
            }
        ),
        label="Descripción",
    )


class ResolveForm(forms.Form):
    """Form for staff to resolve a flag."""

    action_type = forms.ChoiceField(
        choices=ActionType.choices,
        label="Acción",
    )
    notes = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Notas internas..."}),
        label="Notas",
    )
