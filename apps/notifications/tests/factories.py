import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification, NotificationType


class NotificationFactory(DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    sender = factory.SubFactory(UserFactory)
    notification_type = NotificationType.VOTE_RECEIVED
    title = factory.Faker("sentence", nb_words=5)
    message = factory.Faker("text", max_nb_chars=200)
    is_read = False
    link = "/projects/"
