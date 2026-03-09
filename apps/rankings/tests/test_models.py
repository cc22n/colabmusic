from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.tests.factories import UserFactory
from apps.projects.tests.factories import FinalMixFactory
from apps.rankings.models import RankingCache, ReputationLog, Vote
from apps.rankings.tests.factories import (
    RankingCacheFactory,
    ReputationLogFactory,
    VoteFactory,
)


class VoteModelTest(TestCase):
    def test_create_vote(self):
        mix = FinalMixFactory()
        user = UserFactory()
        ct = ContentType.objects.get_for_model(mix)
        vote = Vote.objects.create(
            user=user,
            content_type=ct,
            object_id=mix.pk,
            vote_type=Vote.VoteType.UPVOTE,
        )
        self.assertEqual(vote.vote_type, Vote.VoteType.UPVOTE)
        self.assertIn(user.username, str(vote))

    def test_vote_unique_together(self):
        mix = FinalMixFactory()
        user = UserFactory()
        ct = ContentType.objects.get_for_model(mix)
        Vote.objects.create(user=user, content_type=ct, object_id=mix.pk)
        with self.assertRaises(IntegrityError):
            Vote.objects.create(user=user, content_type=ct, object_id=mix.pk)

    def test_vote_str(self):
        mix = FinalMixFactory()
        ct = ContentType.objects.get_for_model(mix)
        vote = VoteFactory(content_type=ct, object_id=mix.pk)
        self.assertIn("upvote", str(vote))


class RankingCacheModelTest(TestCase):
    def test_create_ranking_cache(self):
        cache = RankingCacheFactory()
        self.assertEqual(cache.ranking_type, "global")
        self.assertIn("global", str(cache))
        self.assertEqual(cache.entries, [])


class ReputationLogModelTest(TestCase):
    def test_create_reputation_log(self):
        log = ReputationLogFactory(points=10, reason="Upvote recibido")
        self.assertIn(log.user.username, str(log))
        self.assertIn("+10", str(log))

    def test_negative_points_str(self):
        log = ReputationLogFactory(points=-2, reason="Downvote recibido")
        self.assertIn("-2", str(log))
