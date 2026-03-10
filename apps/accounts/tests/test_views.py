"""
Tests for accounts views.
ProfileDetailView: public profile, 404, is_own_profile flag.
ProfileUpdateView: auth required, GET/POST behaviour, always own profile.
"""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory, UserProfileFactory


class ProfileDetailViewTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        # Signal creates profile automatically; update display_name for assertions
        self.profile = self.user.profile
        self.profile.display_name = "ArtistName"
        self.profile.save()
        self.url = reverse("accounts:profile", kwargs={"username": self.user.username})

    def test_get_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "accounts/profile.html")

    def test_profile_in_context(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context["profile"], self.profile)

    def test_nonexistent_user_returns_404(self):
        url = reverse("accounts:profile", kwargs={"username": "nobody_here"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_is_own_profile_true_for_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTrue(response.context["is_own_profile"])

    def test_is_own_profile_false_for_other_user(self):
        other = UserFactory()
        self.client.force_login(other)
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_own_profile"])

    def test_is_own_profile_false_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_own_profile"])


class ProfileUpdateViewTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.profile = self.user.profile
        self.url = reverse("accounts:settings")

    def test_get_requires_login_redirects_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_returns_200_for_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "accounts/settings.html")

    def test_post_updates_display_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {
                "display_name": "New Artista",
                "bio": "",
                "roles": [],
                "genres": [],
            },
        )
        # On success, redirects back to settings
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.display_name, "New Artista")

    def test_settings_always_returns_own_profile(self):
        """Authenticated user cannot access another user's profile via /settings/."""
        other_user = UserFactory()
        other_profile = other_user.profile
        other_profile.display_name = "OtherArtist"
        other_profile.save()

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        # The form object should be for self.user's profile, not other_user's
        self.assertEqual(response.context["object"], self.profile)
        self.assertNotEqual(response.context["object"], other_profile)
