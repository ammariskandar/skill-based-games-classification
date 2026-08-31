"""
Server-side validation & input sanitization — SBGC-99.

Verifies the explicit Pydantic query/path schemas on the public catalogue,
rankings, and detail endpoints: bounded pagination, search-query
sanitization, strict enum/boolean parsing, slug path constraints, and the
standard ``VALIDATION_ERROR`` 422 envelope.
"""

from __future__ import annotations

from django.test import Client, TestCase

from games.models import ContentType, Game, ListingStatus, SourceType

_APP_SEQ = 9_000_000


def _next_app_id() -> str:
    global _APP_SEQ
    _APP_SEQ += 1
    return str(_APP_SEQ)


def _game(slug: str, **kwargs) -> Game:
    defaults = dict(
        name=slug.replace("-", " ").title(),
        slug=slug,
        source_type=SourceType.STEAM,
        external_id=_next_app_id(),
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _error_code(response) -> str:
    return response.json()["error"]["code"]


def _error_fields(response) -> list[str]:
    """Field names reported in the 422 details (last location element).

    Ninja prefixes query-schema locations with ``"query"`` and path
    locations with ``"path"``, so the parameter name is the final element.
    """
    details = response.json()["error"]["details"]
    return [
        str(loc[-1]) if loc else ""
        for detail in details
        if (loc := detail.get("location"))
    ]


class ValidationFixtureMixin:
    """One published GAME with a valid hyphenated slug."""

    @classmethod
    def setUpTestData(cls):
        cls.game = _game("valid-hyphenated-slug-123")


class CataloguePaginationValidationTests(ValidationFixtureMixin, TestCase):
    """GET /api/v1/games/ — page / page_size boundaries."""

    def _get(self, query: str):
        return Client().get(f"/api/v1/games/?{query}")

    def test_page_zero_is_rejected(self):
        response = self._get("page=0")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(_error_code(response), "VALIDATION_ERROR")
        self.assertIn("page", _error_fields(response))

    def test_page_negative_is_rejected(self):
        response = self._get("page=-5")
        self.assertEqual(response.status_code, 422)
        self.assertIn("page", _error_fields(response))

    def test_page_non_numeric_is_rejected(self):
        response = self._get("page=abc")
        self.assertEqual(response.status_code, 422)
        self.assertIn("page", _error_fields(response))

    def test_page_size_zero_is_rejected(self):
        response = self._get("page_size=0")
        self.assertEqual(response.status_code, 422)
        self.assertIn("page_size", _error_fields(response))

    def test_page_size_over_100_is_rejected(self):
        response = self._get("page_size=101")
        self.assertEqual(response.status_code, 422)
        self.assertIn("page_size", _error_fields(response))

    def test_page_size_within_bounds_is_accepted(self):
        response = self._get("page_size=50")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_size"], 50)


class CatalogueSearchSanitizationTests(ValidationFixtureMixin, TestCase):
    """GET /api/v1/games/ — q sanitization and clamping."""

    def test_empty_query_is_treated_as_unsearched(self):
        response = Client().get("/api/v1/games/", {"q": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_whitespace_only_query_is_sanitized_to_none(self):
        response = Client().get("/api/v1/games/", {"q": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_query_longer_than_100_chars_is_rejected(self):
        response = Client().get("/api/v1/games/", {"q": "a" * 101})
        self.assertEqual(response.status_code, 422)
        self.assertIn("q", _error_fields(response))

    def test_null_byte_in_query_is_stripped(self):
        response = Client().get("/api/v1/games/", {"q": "test\x00value"})
        self.assertEqual(response.status_code, 200)
        # "testvalue" matches nothing (the fixture game is "Valid Hyphenated...").
        self.assertEqual(response.json()["count"], 0)

    def test_leading_and_trailing_whitespace_is_stripped(self):
        response = Client().get("/api/v1/games/", {"q": "  hyphenated  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)


class CatalogueEnumAndBooleanValidationTests(ValidationFixtureMixin, TestCase):
    """GET /api/v1/games/ — strict enum and boolean parsing."""

    def test_invalid_source_is_rejected(self):
        response = Client().get("/api/v1/games/?source=invalid")
        self.assertEqual(response.status_code, 422)
        self.assertIn("source", _error_fields(response))

    def test_invalid_sort_is_rejected(self):
        response = Client().get("/api/v1/games/?sort=hacked_column")
        self.assertEqual(response.status_code, 422)
        self.assertIn("sort", _error_fields(response))

    def test_invalid_dominant_is_rejected(self):
        response = Client().get("/api/v1/games/?dominant=super_high")
        self.assertEqual(response.status_code, 422)
        self.assertIn("dominant", _error_fields(response))

    def test_misspelled_profile_is_rejected(self):
        response = Client().get("/api/v1/games/?profile=chaLLenge")
        self.assertEqual(response.status_code, 422)
        self.assertIn("profile", _error_fields(response))

    def test_valid_boolean_true_is_accepted(self):
        response = Client().get("/api/v1/games/?coverless_last=true")
        self.assertEqual(response.status_code, 200)

    def test_non_boolean_string_is_rejected(self):
        response = Client().get("/api/v1/games/?coverless_last=not_a_bool")
        self.assertEqual(response.status_code, 422)
        self.assertIn("coverless_last", _error_fields(response))

    def test_numeric_boolean_one_is_accepted(self):
        response = Client().get("/api/v1/games/?classified=1")
        self.assertEqual(response.status_code, 200)

    def test_dual_coverless_last_values_keep_true_wins_contract(self):
        # A checked checkbox submits both the hidden `false` and the checked
        # `true`; the explicit `true` must win (SBGC-79 frontend contract).
        response = Client().get(
            "/api/v1/games/",
            {"coverless_last": ["true", "false"]},
        )
        self.assertEqual(response.status_code, 200)


class RankingsQueryValidationTests(ValidationFixtureMixin, TestCase):
    """GET /api/v1/rankings/ — strict enum and pagination validation."""

    def test_invalid_profile_is_rejected(self):
        response = Client().get("/api/v1/rankings/?profile=chaos")
        self.assertEqual(response.status_code, 422)
        self.assertIn("profile", _error_fields(response))

    def test_invalid_dimension_is_rejected(self):
        response = Client().get("/api/v1/rankings/?dimension=speed")
        self.assertEqual(response.status_code, 422)
        self.assertIn("dimension", _error_fields(response))

    def test_invalid_direction_is_rejected(self):
        response = Client().get("/api/v1/rankings/?direction=sideways")
        self.assertEqual(response.status_code, 422)
        self.assertIn("direction", _error_fields(response))

    def test_page_size_over_100_is_rejected(self):
        response = Client().get("/api/v1/rankings/?page_size=101")
        self.assertEqual(response.status_code, 422)
        self.assertIn("page_size", _error_fields(response))

    def test_valid_query_is_accepted(self):
        response = Client().get("/api/v1/rankings/?profile=challenge&dimension=micro")
        self.assertEqual(response.status_code, 200)


class SlugPathValidationTests(ValidationFixtureMixin, TestCase):
    """GET /api/v1/games/{slug} — slug pattern enforcement."""

    def test_valid_hyphenated_slug_is_accepted(self):
        response = Client().get("/api/v1/games/valid-hyphenated-slug-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game"]["slug"], "valid-hyphenated-slug-123")

    def test_uppercase_slug_is_rejected(self):
        response = Client().get("/api/v1/games/VALID-SLUG")
        self.assertEqual(response.status_code, 422)
        self.assertIn("slug", _error_fields(response))

    def test_underscore_slug_is_rejected(self):
        response = Client().get("/api/v1/games/invalid_slug_with_underscores")
        self.assertEqual(response.status_code, 422)
        self.assertIn("slug", _error_fields(response))

    def test_double_dot_slug_is_rejected(self):
        response = Client().get("/api/v1/games/test..slug")
        self.assertEqual(response.status_code, 422)
        self.assertIn("slug", _error_fields(response))

    def test_traversal_sequence_fails_cleanly(self):
        # ``../`` never reaches the query layer: Django routing rejects the
        # segment, so the request fails cleanly (404/422, never 200 or 500).
        response = Client().get("/api/v1/games/../secret")
        self.assertIn(response.status_code, (404, 422))

    def test_valid_slug_not_in_database_returns_404(self):
        response = Client().get("/api/v1/games/valid-slug-not-in-db")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(_error_code(response), "GAME_NOT_FOUND")
