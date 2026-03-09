from django.test import SimpleTestCase


class SearchAppPlaceholderTest(SimpleTestCase):
    """Search app has no models — uses django-watson with other apps' models."""

    def test_placeholder(self):
        self.assertTrue(True)
