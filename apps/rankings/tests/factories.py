import factory
from django.contrib.contenttypes.models import ContentType
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import GenreFactory, RoleFactory, UserFactory
from apps.rankings.models import RankingCache, ReputationLog, Vote


class VoteFactory(DjangoModelFactory):
    class Meta:
        model = Vote

    user = factory.SubFactory(UserFactory)
    content_type = factory.LazyFunction(
        lambda: ContentType.objects.get_for_model(
            __import__("apps.projects.models", fromlist=["FinalMix"]).FinalMix
        )
    )
    object_id = factory.Sequence(lambda n: n + 1)
    vote_type = Vote.VoteType.UPVOTE


class RankingCacheFactory(DjangoModelFactory):
    class Meta:
        model = RankingCache

    ranking_type = "global"
    period = "weekly"
    genre = None
    role = None
    entries = factory.LazyFunction(list)


class ReputationLogFactory(DjangoModelFactory):
    class Meta:
        model = ReputationLog

    user = factory.SubFactory(UserFactory)
    points = 10
    reason = factory.Faker("sentence", nb_words=5)
