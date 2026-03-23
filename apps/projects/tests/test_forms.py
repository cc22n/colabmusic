"""
Tests for ProjectForm — specifically the genre_custom / Otro genre flow.
"""

from django.test import TestCase

from apps.accounts.models import Genre
from apps.accounts.tests.factories import UserFactory
from apps.projects.forms import ProjectForm
from apps.projects.tests.factories import ProjectFactory


def _base_data(**overrides):
    """Minimal valid POST data for ProjectForm."""
    return {
        "title": "Mi Proyecto",
        "description": "",
        "project_type": "original",
        "is_public": True,
        "allow_multiple_versions": False,
        "tags": "",
        **overrides,
    }


class ProjectFormGenreCustomTest(TestCase):
    def setUp(self):
        # Ensure "Otro" sentinel exists (migration may not run in test DB)
        self.otro, _ = Genre.objects.get_or_create(
            slug="otro", defaults={"name": "Otro"}
        )
        self.pop, _ = Genre.objects.get_or_create(
            slug="pop", defaults={"name": "Pop"}
        )

    def test_known_genre_accepted_without_custom(self):
        data = _base_data(genre=self.pop.pk)
        form = ProjectForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["genre"], self.pop)

    def test_otro_without_custom_raises_error(self):
        data = _base_data(genre=self.otro.pk, genre_custom="")
        form = ProjectForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("genre_custom", form.errors)

    def test_otro_with_new_genre_creates_it(self):
        data = _base_data(genre=self.otro.pk, genre_custom="Bossa Nova")
        form = ProjectForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        resolved = form.cleaned_data["genre"]
        self.assertEqual(resolved.slug, "bossa-nova")
        self.assertTrue(Genre.objects.filter(slug="bossa-nova").exists())

    def test_otro_with_existing_genre_reuses_it(self):
        """If the typed name matches an existing genre slug, it reuses it."""
        Genre.objects.get_or_create(slug="jazz", defaults={"name": "Jazz"})
        data = _base_data(genre=self.otro.pk, genre_custom="Jazz")
        form = ProjectForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["genre"].slug, "jazz")
        # No duplicate created
        self.assertEqual(Genre.objects.filter(slug="jazz").count(), 1)

    def test_otro_genre_name_is_title_cased(self):
        data = _base_data(genre=self.otro.pk, genre_custom="afrobeat cubano")
        form = ProjectForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        created = Genre.objects.get(slug="afrobeat-cubano")
        self.assertEqual(created.name, "Afrobeat Cubano")

    def test_genre_custom_ignored_when_not_otro(self):
        """genre_custom should be silently ignored if Otro is not selected."""
        data = _base_data(genre=self.pop.pk, genre_custom="Reggaeton")
        form = ProjectForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["genre"], self.pop)
