"""
Tests for rankings Celery tasks.
calculate_rankings: populates RankingCache for global, by_role, by_genre, covers.
award_top10_weekly_bonus: awards +100 to top-10 users; no-op when cache missing.
"""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.accounts.tests.factories import GenreFactory, RoleFactory, UserFactory
from apps.projects.tests.factories import FinalMixFactory, ProjectFactory
from apps.rankings.models import RankingCache, ReputationLog, Vote
from apps.rankings.tasks import award_top10_weekly_bonus, calculate_rankings


class CalculateRankingsGlobalTest(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.profile.reputation_score = 50
        self.user.profile.save()

    def test_creates_global_ranking_cache(self):
        calculate_rankings("weekly")
        self.assertTrue(
            RankingCache.objects.filter(ranking_type="global", period="weekly").exists()
        )

    def test_global_entries_contain_user(self):
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="global", period="weekly", genre=None, role=None
        )
        usernames = [e["username"] for e in cache.entries]
        self.assertIn(self.user.username, usernames)

    def test_global_entries_sorted_by_reputation(self):
        high = UserFactory()
        high.profile.reputation_score = 200
        high.profile.save()
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="global", period="weekly", genre=None, role=None
        )
        scores = [e["reputation_score"] for e in cache.entries]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_second_call_updates_not_duplicates(self):
        calculate_rankings("weekly")
        calculate_rankings("weekly")
        self.assertEqual(
            RankingCache.objects.filter(ranking_type="global", period="weekly").count(),
            1,
        )


class CalculateRankingsByRoleTest(TestCase):
    def setUp(self):
        self.role = RoleFactory()
        self.user = UserFactory()
        self.user.profile.roles.add(self.role)
        self.user.profile.reputation_score = 30
        self.user.profile.save()

    def test_creates_by_role_cache(self):
        calculate_rankings("weekly")
        self.assertTrue(
            RankingCache.objects.filter(
                ranking_type="by_role", period="weekly", role=self.role
            ).exists()
        )

    def test_by_role_entries_contain_role_user(self):
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="by_role", period="weekly", role=self.role, genre=None
        )
        usernames = [e["username"] for e in cache.entries]
        self.assertIn(self.user.username, usernames)

    def test_by_role_excludes_other_role_users(self):
        other_role = RoleFactory(name="vocalist")
        other_user = UserFactory()
        other_user.profile.roles.add(other_role)
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="by_role", period="weekly", role=self.role, genre=None
        )
        usernames = [e["username"] for e in cache.entries]
        self.assertNotIn(other_user.username, usernames)


class CalculateRankingsByGenreTest(TestCase):
    def setUp(self):
        self.genre = GenreFactory()
        self.project = ProjectFactory(genre=self.genre, is_public=True)

    def test_creates_by_genre_cache(self):
        calculate_rankings("weekly")
        self.assertTrue(
            RankingCache.objects.filter(
                ranking_type="by_genre", period="weekly", genre=self.genre
            ).exists()
        )

    def test_by_genre_entries_contain_project(self):
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="by_genre", period="weekly", genre=self.genre, role=None
        )
        slugs = [e["slug"] for e in cache.entries]
        self.assertIn(self.project.slug, slugs)


class CalculateRankingsCoversTest(TestCase):
    def setUp(self):
        self.cover = ProjectFactory(project_type="cover", is_public=True)
        self.original = ProjectFactory(project_type="original", is_public=True)

    def test_creates_covers_cache(self):
        calculate_rankings("weekly")
        self.assertTrue(
            RankingCache.objects.filter(ranking_type="covers", period="weekly").exists()
        )

    def test_covers_entries_contain_only_covers(self):
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="covers", period="weekly", genre=None, role=None
        )
        for entry in cache.entries:
            self.assertEqual(entry["project_type"], "cover")

    def test_covers_entries_ranked_by_mix_upvotes(self):
        """A cover with more FinalMix upvotes ranks higher."""
        popular_cover = ProjectFactory(project_type="cover", is_public=True)
        mix = FinalMixFactory(project=popular_cover)
        voter = UserFactory()
        ct = ContentType.objects.get_for_model(mix)
        Vote.objects.create(
            user=voter,
            content_type=ct,
            object_id=mix.pk,
            vote_type=Vote.VoteType.UPVOTE,
        )
        calculate_rankings("weekly")
        cache = RankingCache.objects.get(
            ranking_type="covers", period="weekly", genre=None, role=None
        )
        # popular_cover should be rank 1
        self.assertEqual(cache.entries[0]["slug"], popular_cover.slug)
        self.assertEqual(cache.entries[0]["upvotes"], 1)


class AwardTop10WeeklyBonusTest(TestCase):
    def test_no_op_when_cache_missing(self):
        """Should not raise when no weekly ranking cache exists."""
        award_top10_weekly_bonus()
        self.assertEqual(ReputationLog.objects.count(), 0)

    def test_awards_100_to_top10_users(self):
        users = [UserFactory() for _ in range(12)]
        entries = [
            {
                "rank": i + 1,
                "user_id": u.pk,
                "username": u.username,
                "display_name": str(u),
                "reputation_score": 100 - i,
                "roles": [],
            }
            for i, u in enumerate(users)
        ]
        RankingCache.objects.create(
            ranking_type="global",
            period="weekly",
            genre=None,
            role=None,
            entries=entries,
        )
        award_top10_weekly_bonus()
        # Only top 10 should receive bonus
        self.assertEqual(ReputationLog.objects.count(), 10)
        for u in users[:10]:
            u.profile.refresh_from_db()
            self.assertEqual(u.profile.reputation_score, 100)
        # 11th and 12th user should NOT receive bonus
        users[10].profile.refresh_from_db()
        self.assertEqual(users[10].profile.reputation_score, 0)

    def test_reputation_log_reason(self):
        user = UserFactory()
        RankingCache.objects.create(
            ranking_type="global",
            period="weekly",
            genre=None,
            role=None,
            entries=[
                {
                    "rank": 1,
                    "user_id": user.pk,
                    "username": user.username,
                    "display_name": str(user),
                    "reputation_score": 500,
                    "roles": [],
                }
            ],
        )
        award_top10_weekly_bonus()
        log = ReputationLog.objects.get(user=user)
        self.assertEqual(log.points, 100)
        self.assertIn("Top 10", log.reason)


class RankingByRoleViewTest(TestCase):
    def setUp(self):
        self.role = RoleFactory()

    def test_get_returns_200(self):
        from django.urls import reverse

        url = reverse("rankings:by-role", kwargs={"role": self.role.name})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_unknown_role_returns_404(self):
        from django.urls import reverse

        url = reverse("rankings:by-role", kwargs={"role": "unknown_role"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class CoverRankingsViewTest(TestCase):
    def test_get_returns_200(self):
        from django.urls import reverse

        url = reverse("rankings:covers")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_uses_rankings_template(self):
        from django.urls import reverse

        url = reverse("rankings:covers")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "rankings/rankings.html")

    def test_is_covers_in_context(self):
        from django.urls import reverse

        url = reverse("rankings:covers")
        response = self.client.get(url)
        self.assertTrue(response.context["is_covers"])
