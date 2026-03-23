"""
Data migration: seed common music genres.
Includes an 'Otro' sentinel entry so users can type a custom genre
from the project creation form.
"""

from django.db import migrations
from django.utils.text import slugify

GENRES = [
    "Pop",
    "Rock",
    "Hip-Hop / Rap",
    "R&B / Soul",
    "Electronic / EDM",
    "Jazz",
    "Blues",
    "Reggaeton",
    "Salsa",
    "Cumbia",
    "Bachata",
    "Balada",
    "Folk / Acústico",
    "Metal",
    "Indie",
    "Clásica",
    "Funk",
    "Tropical",
    "Urbano",
    "Experimental",
    "Otro",  # sentinel — triggers the custom-genre text input in the form
]


def seed_genres(apps, schema_editor):
    Genre = apps.get_model("accounts", "Genre")
    for name in GENRES:
        Genre.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name},
        )


def delete_genres(apps, schema_editor):
    Genre = apps.get_model("accounts", "Genre")
    slugs = [slugify(n) for n in GENRES]
    # Only delete genres that have no associated projects to be safe
    Genre.objects.filter(slug__in=slugs, projects__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_seed_roles"),
    ]

    operations = [
        migrations.RunPython(seed_genres, delete_genres),
    ]
