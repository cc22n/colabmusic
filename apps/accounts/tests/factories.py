import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from apps.accounts.models import Badge, Genre, Role, UserBadge, UserProfile

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class RoleFactory(DjangoModelFactory):
    class Meta:
        model = Role
        django_get_or_create = ["name"]

    name = Role.RoleName.LYRICIST
    display_name = factory.LazyAttribute(lambda obj: obj.name.title())
    description = factory.Faker("sentence")
    icon = "music-note"


class GenreFactory(DjangoModelFactory):
    class Meta:
        model = Genre
        django_get_or_create = ["slug"]

    name = factory.Sequence(lambda n: f"Genre {n}")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))
    parent = None


class UserProfileFactory(DjangoModelFactory):
    class Meta:
        model = UserProfile
        django_get_or_create = ["user"]

    user = factory.SubFactory(UserFactory)
    display_name = factory.Faker("user_name")
    bio = factory.Faker("text", max_nb_chars=200)
    reputation_score = 0


class BadgeFactory(DjangoModelFactory):
    class Meta:
        model = Badge

    name = factory.Sequence(lambda n: f"Badge {n}")
    condition = factory.Faker("sentence")
    description = factory.Faker("text", max_nb_chars=100)


class UserBadgeFactory(DjangoModelFactory):
    class Meta:
        model = UserBadge

    user = factory.SubFactory(UserFactory)
    badge = factory.SubFactory(BadgeFactory)
