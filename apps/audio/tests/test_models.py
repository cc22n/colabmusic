from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.audio.models import AudioProcessingTask
from apps.projects.tests.factories import BeatFactory


class AudioProcessingTaskModelTest(TestCase):
    def test_create_task(self):
        beat = BeatFactory()
        ct = ContentType.objects.get_for_model(beat)
        task = AudioProcessingTask.objects.create(
            content_type=ct,
            object_id=beat.pk,
            celery_task_id="test-uuid-123",
        )
        self.assertEqual(task.status, AudioProcessingTask.TaskStatus.QUEUED)
        self.assertEqual(task.attempts, 0)

    def test_task_str(self):
        beat = BeatFactory()
        ct = ContentType.objects.get_for_model(beat)
        task = AudioProcessingTask.objects.create(
            content_type=ct,
            object_id=beat.pk,
        )
        self.assertIn("queued", str(task))
        self.assertIn("beat", str(task).lower())
