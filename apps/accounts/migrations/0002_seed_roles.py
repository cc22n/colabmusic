"""
Data migration: create the three default musical roles.
These must exist before users can register with a role selection.
"""

from django.db import migrations


ROLES = [
    {
        "name": "lyricist",
        "display_name": "Letrista",
        "description": "Escribe las letras de las canciones.",
        "icon": "✍️",
    },
    {
        "name": "producer",
        "display_name": "Productor",
        "description": "Produce los beats e instrumentales.",
        "icon": "🎹",
    },
    {
        "name": "vocalist",
        "display_name": "Vocalista",
        "description": "Graba y edita las pistas vocales.",
        "icon": "🎤",
    },
]


def create_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for role_data in ROLES:
        Role.objects.get_or_create(
            name=role_data["name"],
            defaults={
                "display_name": role_data["display_name"],
                "description": role_data["description"],
                "icon": role_data["icon"],
            },
        )


def delete_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(name__in=[r["name"] for r in ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_roles, delete_roles),
    ]
