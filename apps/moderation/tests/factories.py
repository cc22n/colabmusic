import factory
from django.contrib.contenttypes.models import ContentType
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.moderation.models import Flag, FlagReason, FlagStatus, ModerationAction, ActionType
from apps.projects.tests.factories import LyricsFactory


class FlagFactory(DjangoModelFactory):
    class Meta:
        model = Flag

    reporter = factory.SubFactory(UserFactory)
    content_type = factory.LazyAttribute(
        lambda obj: ContentType.objects.get_for_model(obj.content_object)
        if obj.content_object
        else ContentType.objects.get_for_model(
            __import__("apps.projects.models", fromlist=["Lyrics"]).Lyrics
        )
    )
    object_id = factory.SelfAttribute("content_object.pk")
    reason = FlagReason.SPAM
    description = ""
    status = FlagStatus.PENDING

    class Params:
        content_object = factory.SubFactory(LyricsFactory)


class ModerationActionFactory(DjangoModelFactory):
    class Meta:
        model = ModerationAction

    flag = factory.SubFactory(FlagFactory)
    moderator = factory.SubFactory(UserFactory)
    action_type = ActionType.DISMISS
    notes = ""
