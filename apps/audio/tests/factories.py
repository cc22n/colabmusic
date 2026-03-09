import factory
from django.contrib.contenttypes.models import ContentType
from factory.django import DjangoModelFactory

from apps.audio.models import AudioProcessingTask


class AudioProcessingTaskFactory(DjangoModelFactory):
    class Meta:
        model = AudioProcessingTask

    content_type = factory.LazyFunction(
        lambda: ContentType.objects.get_for_model(
            __import__("apps.projects.models", fromlist=["Beat"]).Beat
        )
    )
    object_id = factory.Sequence(lambda n: n + 1)
    celery_task_id = factory.Faker("uuid4")
    status = AudioProcessingTask.TaskStatus.QUEUED
    attempts = 0
