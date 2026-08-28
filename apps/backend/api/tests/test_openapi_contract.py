"""
Cross-boundary OpenAPI contract tests — SBGC-93.

Guards the live Django Ninja OpenAPI document against the field-level contract
the Astro frontend depends on (mirrored in ``apps/frontend/src/types/api.ts``
and the committed OpenAPI fixture under the frontend test suite).  These are
read-only assertions against ``/api/v1/openapi.json`` — no database is touched,
and no network requests are made.

The frontend runs an equivalent static suite against an exported copy of this
document; this suite is the live-side guard that the two stay aligned.
"""

from django.test import Client, SimpleTestCase

PUBLIC_GAME_DETAIL_FIELDS = {
    "id",
    "slug",
    "name",
    "source",
    "external_id",
    "content_type",
    "description",
    "release_date",
    "developer",
    "image_url",
    "library_hero_url",
    "library_capsule_url",
    "metadata_updated_at",
}

PUBLIC_FINAL_CLASSIFICATION_FIELDS = {
    "status",
    "regime",
    "challenge",
    "reward",
    "confidence_level",
    "confidence_label",
    "submission_count",
    "calculation_version",
    "calculated_at",
    "is_stale",
}

PUBLIC_CLASSIFICATION_PROFILE_FIELDS = {"micro", "macro", "mystiko"}
GAME_DETAIL_RESPONSE_FIELDS = {"game", "classification"}
GAME_CATALOGUE_ITEM_FIELDS = {
    "slug",
    "name",
    "source",
    "image_url",
    "library_capsule_url",
    "classification",
}
GAME_CATALOGUE_RESPONSE_FIELDS = {
    "count",
    "page",
    "page_size",
    "total_pages",
    "results",
}
SEARCH_INDEX_ITEM_FIELDS = {"slug", "name", "capsule_url", "image_url"}
SEARCH_INDEX_RESPONSE_FIELDS = {"games"}
RANKING_ITEM_FIELDS = {"slug", "name", "hero_url", "score"}
RANKING_RESPONSE_FIELDS = {"count", "page", "page_size", "total_pages", "results"}
API_ERROR_FIELDS = {"code", "message", "details"}
API_ERROR_DETAIL_FIELDS = {"location", "message", "type"}
API_ERROR_RESPONSE_FIELDS = {"error"}


class OpenApiContractTests(SimpleTestCase):
    """Field-level parity between the live OpenAPI doc and the frontend DTOs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        client = Client()
        document = client.get("/api/v1/openapi.json").json()
        cls.paths = document["paths"]
        cls.schemas = document["components"]["schemas"]

    def _success_ref(self, path: str) -> str:
        return self.paths[path]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]

    def _property_names(self, name: str) -> set[str]:
        return set(self.schemas[name]["properties"].keys())

    def _required(self, name: str) -> set[str]:
        return set(self.schemas[name].get("required", []))

    def _assert_properties(self, name: str, expected: set[str]) -> None:
        self.assertEqual(self._property_names(name), expected)

    def test_public_endpoints_are_registered(self):
        self.assertEqual(
            self._success_ref("/api/v1/games/{slug}"),
            "#/components/schemas/GameDetailResponse",
        )
        self.assertEqual(
            self._success_ref("/api/v1/games/"),
            "#/components/schemas/GameCatalogueResponse",
        )
        self.assertEqual(
            self._success_ref("/api/v1/rankings/"),
            "#/components/schemas/RankingResponse",
        )
        self.assertEqual(
            self._success_ref("/api/v1/games/search-index"),
            "#/components/schemas/SearchIndexResponse",
        )

    def test_public_game_detail_contract(self):
        self._assert_properties("PublicGameDetail", PUBLIC_GAME_DETAIL_FIELDS)
        self.assertNotIn("publisher", self._property_names("PublicGameDetail"))
        self.assertEqual(
            self._required("PublicGameDetail"),
            PUBLIC_GAME_DETAIL_FIELDS - {"library_hero_url", "library_capsule_url"},
        )

        self._assert_properties(
            "PublicFinalClassification", PUBLIC_FINAL_CLASSIFICATION_FIELDS
        )
        self.assertEqual(self._required("PublicFinalClassification"), {"status"})

        self._assert_properties(
            "PublicClassificationProfile", PUBLIC_CLASSIFICATION_PROFILE_FIELDS
        )
        self.assertEqual(
            self._required("PublicClassificationProfile"),
            PUBLIC_CLASSIFICATION_PROFILE_FIELDS,
        )

        self._assert_properties("GameDetailResponse", GAME_DETAIL_RESPONSE_FIELDS)
        self.assertEqual(self._required("GameDetailResponse"), {"game"})

    def test_catalogue_contract(self):
        self._assert_properties("GameCatalogueItem", GAME_CATALOGUE_ITEM_FIELDS)
        self.assertNotIn("id", self._property_names("GameCatalogueItem"))
        self.assertEqual(
            self._required("GameCatalogueItem"),
            {"slug", "name", "source", "image_url"},
        )

        self._assert_properties("GameCatalogueResponse", GAME_CATALOGUE_RESPONSE_FIELDS)
        self.assertEqual(
            self._required("GameCatalogueResponse"), GAME_CATALOGUE_RESPONSE_FIELDS
        )

    def test_rankings_contract(self):
        self._assert_properties("RankingItem", RANKING_ITEM_FIELDS)
        self.assertEqual(self._required("RankingItem"), RANKING_ITEM_FIELDS)

        self._assert_properties("RankingResponse", RANKING_RESPONSE_FIELDS)
        self.assertEqual(self._required("RankingResponse"), RANKING_RESPONSE_FIELDS)

    def test_search_index_contract(self):
        self._assert_properties("SearchIndexItem", SEARCH_INDEX_ITEM_FIELDS)
        self.assertEqual(self._required("SearchIndexItem"), {"slug", "name"})

        self._assert_properties("SearchIndexResponse", SEARCH_INDEX_RESPONSE_FIELDS)
        self.assertEqual(self._required("SearchIndexResponse"), {"games"})

    def test_error_envelope_contract(self):
        self._assert_properties("ApiError", API_ERROR_FIELDS)
        self.assertEqual(self._required("ApiError"), {"code", "message"})

        self._assert_properties("ApiErrorDetail", API_ERROR_DETAIL_FIELDS)
        self.assertEqual(self._required("ApiErrorDetail"), API_ERROR_DETAIL_FIELDS)

        self._assert_properties("ApiErrorResponse", API_ERROR_RESPONSE_FIELDS)
        self.assertEqual(self._required("ApiErrorResponse"), {"error"})
