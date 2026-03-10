"""
Tests for rankings views.
RankingsView, TrendingView: GET returns 200.
cast_vote: auth required, upvote creates Vote + ReputationLog,
           toggle deletes Vote + reverts reputation, GET returns 405,
           invalid content_type returns 400.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.projects.tests.factories import LyricsFactory, ProjectFactory
from apps.rankings.models import ReputationLog, Vote


class RankingsViewTests(TestCase):
    def test_get_returns_200(self):
        url = reverse("rankings:global")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_uses_rankings_template(self):
        url = reverse("rankings:global")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "rankings/rankings.html")

    def test_is_trending_false(self):
        url = reverse("rankings:global")
        response = self.client.get(url)
        self.assertFalse(response.context["is_trending"])


class TrendingViewTests(TestCase):
    def test_get_returns_200(self):
        url = reverse("rankings:trending")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_uses_rankings_template(self):
        url = reverse("rankings:trending")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "rankings/rankings.html")

    def test_is_trending_true(self):
        url = reverse("rankings:trending")
        response = self.client.get(url)
        self.assertTrue(response.context["is_trending"])


class CastVoteTests(TestCase):
    def setUp(self):
        self.voter = UserFactory()
        self.author = UserFactory()
        # Lyrics project owned by author
        self.project = ProjectFactory(
            created_by=self.author,
            status="seeking_lyrics",
        )
        self.lyrics = LyricsFactory(project=self.project, author=self.author)
        self.url = reverse(
            "rankings:cast-vote",
            kwargs={"content_type_str": "lyrics", "object_id": self.lyrics.pk},
        )

    def _post(self, vote_type=Vote.VoteType.UPVOTE, user=None):
        if user:
            self.client.force_login(user)
        return self.client.post(self.url, {"vote_type": vote_type})

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_anonymous_redirects_to_login(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    # ── GET not allowed ───────────────────────────────────────────────────────

    def test_get_returns_405(self):
        self.client.force_login(self.voter)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # ── Invalid content type ──────────────────────────────────────────────────

    def test_invalid_content_type_returns_400(self):
        self.client.force_login(self.voter)
        url = reverse(
            "rankings:cast-vote",
            kwargs={"content_type_str": "invalid_type", "object_id": self.lyrics.pk},
        )
        response = self.client.post(url, {"vote_type": Vote.VoteType.UPVOTE})
        self.assertEqual(response.status_code, 400)

    # ── New upvote ────────────────────────────────────────────────────────────

    def test_upvote_creates_vote(self):
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        ct = ContentType.objects.get(app_label="projects", model="lyrics")
        self.assertTrue(
            Vote.objects.filter(
                user=self.voter,
                content_type=ct,
                object_id=self.lyrics.pk,
                vote_type=Vote.VoteType.UPVOTE,
            ).exists()
        )

    def test_upvote_adds_reputation_to_author(self):
        initial = self.author.profile.reputation_score
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        self.author.profile.refresh_from_db()
        self.assertEqual(self.author.profile.reputation_score, initial + 10)

    def test_upvote_creates_reputation_log(self):
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        self.assertTrue(
            ReputationLog.objects.filter(user=self.author, points=10).exists()
        )

    # ── Toggle off ────────────────────────────────────────────────────────────

    def test_same_vote_toggles_off(self):
        """Voting the same type twice removes the vote."""
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        ct = ContentType.objects.get(app_label="projects", model="lyrics")
        self.assertTrue(
            Vote.objects.filter(
                user=self.voter, content_type=ct, object_id=self.lyrics.pk
            ).exists()
        )
        # Vote again with same type → toggle off
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        self.assertFalse(
            Vote.objects.filter(
                user=self.voter, content_type=ct, object_id=self.lyrics.pk
            ).exists()
        )

    def test_toggle_reverts_reputation(self):
        """After toggle off, reputation returns to initial value."""
        initial = self.author.profile.reputation_score
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        self._post(Vote.VoteType.UPVOTE, user=self.voter)
        self.author.profile.refresh_from_db()
        self.assertEqual(self.author.profile.reputation_score, initial)

    # ── Self-vote no reputation ───────────────────────────────────────────────

    def test_self_vote_does_not_change_reputation(self):
        """A user voting on their own content gains no reputation."""
        initial = self.author.profile.reputation_score
        self._post(Vote.VoteType.UPVOTE, user=self.author)
        self.author.profile.refresh_from_db()
        self.assertEqual(self.author.profile.reputation_score, initial)
