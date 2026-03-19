"""
Tests for apps.search views.

Uses `watson.update_index()` context manager so the search engine
indexes objects created inside the block.
"""

from watson.search import update_index as watson_update_index
from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import GenreFactory, UserFactory, UserProfileFactory
from apps.projects.tests.factories import LyricsFactory, ProjectFactory


HTMX_HEADERS = {"HTTP_HX_REQUEST": "true"}
RESULTS_URL = "/search/results/"
SEARCH_URL = "/search/"


# ---------------------------------------------------------------------------
# SearchView — full page
# ---------------------------------------------------------------------------


class SearchViewTest(TestCase):
    def test_get_returns_200(self):
        """GET /search/ renders the search page."""
        response = self.client.get(SEARCH_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "search/search.html")

    def test_genres_in_context(self):
        """Search page includes the genres queryset."""
        GenreFactory(name="Rock")
        GenreFactory(name="Jazz")
        response = self.client.get(SEARCH_URL)
        self.assertIn("genres", response.context)
        genre_names = list(response.context["genres"].values_list("name", flat=True))
        self.assertIn("Rock", genre_names)
        self.assertIn("Jazz", genre_names)

    def test_q_param_passed_to_context(self):
        """Query string q is forwarded to template context."""
        response = self.client.get(SEARCH_URL + "?q=salsa")
        self.assertEqual(response.context["q"], "salsa")

    def test_type_and_genre_params_in_context(self):
        """type and genre params are forwarded to context."""
        response = self.client.get(SEARCH_URL + "?type=project&genre=rock")
        self.assertEqual(response.context["current_type"], "project")
        self.assertEqual(response.context["current_genre"], "rock")


# ---------------------------------------------------------------------------
# search_results — HTMX partial
# ---------------------------------------------------------------------------


class SearchResultsTest(TestCase):

    def _get(self, params="", **extra):
        """Helper: GET /search/results/ with HTMX header."""
        return self.client.get(RESULTS_URL + params, **{**HTMX_HEADERS, **extra})

    # 1. Non-HTMX request rejected
    def test_non_htmx_returns_400(self):
        """Requests without HX-Request header are rejected with 400."""
        response = self.client.get(RESULTS_URL + "?q=test")
        self.assertEqual(response.status_code, 400)

    # 2. Empty query
    def test_empty_query_returns_empty_list(self):
        """Empty q returns a 200 with empty_query=True context."""
        response = self._get("?q=")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["empty_query"])
        self.assertEqual(list(response.context["results"]), [])

    # 3. Finds a public project
    def test_finds_public_project(self):
        """A public project with matching title appears in results."""
        with watson_update_index():
            ProjectFactory(title="Tropical Cumbia Beat", is_public=True)

        response = self._get("?q=Cumbia")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["empty_query"])
        titles = [e.title for e in response.context["results"]]
        self.assertTrue(
            any("Cumbia" in t for t in titles),
            f"Expected 'Cumbia' in {titles}",
        )

    # 4. Private project excluded
    def test_excludes_private_project(self):
        """Private projects do not appear in search results."""
        with watson_update_index():
            ProjectFactory(title="SecretProjectZZZ", is_public=False)

        response = self._get("?q=SecretProjectZZZ")
        self.assertEqual(response.status_code, 200)
        titles = [e.title for e in response.context["results"]]
        self.assertFalse(
            any("SecretProjectZZZ" in t for t in titles),
            "Private project should not appear in search results",
        )

    # 5. type filter: only projects
    def test_type_filter_project_only(self):
        """type=project filter returns only project-type entries."""
        with watson_update_index():
            ProjectFactory(title="FilterTestProject", is_public=True)
            LyricsFactory(content="FilterTestProject lyrics content here")

        response = self._get("?q=FilterTestProject&type=project")
        self.assertEqual(response.status_code, 200)
        results = list(response.context["results"])
        for entry in results:
            self.assertEqual(
                entry.content_type.model, "project",
                f"Expected model 'project' but got '{entry.content_type.model}'",
            )

    # 6. XSS attempt in query is safe
    def test_xss_in_query_is_safe(self):
        """HTML tags in the query string are stripped; request does not crash."""
        # strip_tags("<script>alert(1)</script>") → "alert(1)", not empty.
        # The important thing: 200 response and no raw <script> in output.
        response = self._get("?q=<script>alert(1)</script>")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<script>", response.content)

    # 7. Very long query is truncated
    def test_long_query_truncated_no_error(self):
        """Queries longer than 200 chars are truncated gracefully."""
        long_q = "a" * 300
        response = self._get(f"?q={long_q}")
        self.assertEqual(response.status_code, 200)

    # 8. limit param for navbar dropdown
    def test_limit_param_for_navbar_dropdown(self):
        """?limit=5 triggers is_dropdown mode in the context."""
        with watson_update_index():
            for i in range(8):
                ProjectFactory(title=f"DropdownProject{i}", is_public=True)

        response = self._get("?q=DropdownProject&limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_dropdown"])
        results = list(response.context["results"])
        self.assertLessEqual(len(results), 5)

    # 9. No results message rendered
    def test_no_results_empty_state(self):
        """A query with no matches returns is_dropdown=False, empty results."""
        response = self._get("?q=xyzzy_nonexistent_99999")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["empty_query"])
        self.assertFalse(response.context["is_dropdown"])

    # 10. Limit clamped to max 20
    def test_limit_clamped_to_20(self):
        """limit param above 20 is clamped to 20."""
        with watson_update_index():
            for i in range(25):
                ProjectFactory(title=f"ClampProject{i}", is_public=True)

        response = self._get("?q=ClampProject&limit=999")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_dropdown"])
        results = list(response.context["results"])
        self.assertLessEqual(len(results), 20)
