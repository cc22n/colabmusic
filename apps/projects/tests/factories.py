import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import GenreFactory, UserFactory
from apps.projects.models import (
    Beat,
    FinalMix,
    Lyrics,
    Project,
    ProjectStatus,
    ProjectType,
    Tag,
    VocalTrack,
)


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"tag{n}")
    slug = factory.LazyAttribute(lambda obj: obj.name)


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    title = factory.Sequence(lambda n: f"Proyecto {n}")
    description = factory.Faker("text", max_nb_chars=300)
    project_type = ProjectType.ORIGINAL
    created_by = factory.SubFactory(UserFactory)
    is_public = True
    allow_multiple_versions = False


class LyricsFactory(DjangoModelFactory):
    class Meta:
        model = Lyrics

    project = factory.SubFactory(ProjectFactory)
    author = factory.SubFactory(UserFactory)
    content = factory.Faker("text", max_nb_chars=500)
    language = "es"
    is_selected = False


class BeatFactory(DjangoModelFactory):
    class Meta:
        model = Beat

    project = factory.SubFactory(ProjectFactory)
    producer = factory.SubFactory(UserFactory)
    original_file = factory.django.FileField(filename="beat.mp3")
    bpm = 120
    key_signature = "Cm"
    is_selected = False


class VocalTrackFactory(DjangoModelFactory):
    class Meta:
        model = VocalTrack

    project = factory.SubFactory(ProjectFactory)
    vocalist = factory.SubFactory(UserFactory)
    original_file = factory.django.FileField(filename="vocal.mp3")
    is_selected = False
    version_number = 1


class FinalMixFactory(DjangoModelFactory):
    class Meta:
        model = FinalMix

    project = factory.SubFactory(ProjectFactory)
    original_file = factory.django.FileField(filename="mix.mp3")
    play_count = 0
    is_featured = False
