"""
Public game-detail endpoint tests — SBGC-71.

Exercises ``GET /api/v1/games/{slug}`` through the full routing stack:
public eligibility, Steam/manual normalization, persisted-only reads,
current Final Classification states, error envelope, and OpenAPI exposure.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.test import Client, TestCase
from django.utils import timezone
from games.models import Game, SourceType


def _game(**kwargs) -> Game:
    defaults = dict(
        name="Test Game",
        slug="test-game",
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _epoch(epoch_id: str = "api-epoch") -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id=epoch_id,
        defaults={
            "cutoff_at": timezone.now(),
            "master_version": "STATISTICAL_MODEL_V1.0.0",
        },
    )
    return epoch


def _snapshot(game: Game, **kwargs) -> ClassificationSnapshot:
    defaults = dict(
        epoch=_epoch(),
        regime="provisional",
        status="READY",
        cutoff_at=timezone.now(),
        is_current=True,
        is_stale=False,
        calculated_at=timezone.now(),
        master_version="STATISTICAL_MODEL_V1.0.0",
        methods_version="METHODS_V1",
        bhpcm_version="BHPCM_V1",
        confidence_final_version="CONFIDENCE_V1",
    )
    defaults.update(kwargs)
    return ClassificationSnapshot.objects.create(game=game, **defaults)


class GameDetailEndpointTests(TestCase):
    def _get(self, slug: str):
        return Client().get(f"/api/v1/games/{slug}")

    # -- A. public Steam Game -----------------------------------------------

    def test_public_steam_game_returns_200(self):
        game = _game(
            name="Counter-Strike 2",
            slug="counter-strike-2",
            source_type=SourceType.STEAM,
            external_id="730",
            developer="Valve",
            steam_image_url="https://example.com/header.jpg",
        )
        r = self._get("counter-strike-2")

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["game"]["id"], game.pk)
        self.assertEqual(body["game"]["slug"], "counter-strike-2")
        self.assertEqual(body["game"]["name"], "Counter-Strike 2")
        self.assertEqual(body["game"]["source"], "steam")
        self.assertEqual(body["game"]["external_id"], "730")
        self.assertEqual(body["game"]["content_type"], "game")
        self.assertEqual(body["game"]["developer"], "Valve")
        self.assertEqual(body["game"]["image_url"], "https://example.com/header.jpg")
        self.assertIsNone(body["game"]["release_date"])
        self.assertIn("metadata_updated_at", body["game"])
        self.assertIsNone(body["classification"])

    def test_public_steam_game_returns_steam_populated_metadata(self):
        _game(
            name="Portal 2",
            slug="portal-2",
            source_type=SourceType.STEAM,
            external_id="620",
            description="A puzzle game.",
            developer="Valve",
            release_date=date(2011, 4, 18),
        )
        r = self._get("portal-2")

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["game"]["description"], "A puzzle game.")
        self.assertEqual(body["game"]["developer"], "Valve")
        self.assertEqual(body["game"]["release_date"], "2011-04-18")

    # -- B. public Manual Game ----------------------------------------------

    def test_public_manual_game_returns_200_with_null_external_id(self):
        _game(
            name="Chess",
            slug="chess",
            source_type=SourceType.MANUAL,
            external_id=None,
            developer="Editorial",
            release_date=date(1475, 1, 1),
            manual_image_url="https://example.com/chess.png",
            description="The classic board game.",
        )
        r = self._get("chess")

        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["game"]["source"], "manual")
        self.assertIsNone(body["game"]["external_id"])
        self.assertEqual(body["game"]["description"], "The classic board game.")
        self.assertEqual(body["game"]["developer"], "Editorial")
        self.assertEqual(body["game"]["release_date"], "1475-01-01")
        self.assertEqual(body["game"]["image_url"], "https://example.com/chess.png")

    # -- C. unknown slug ----------------------------------------------------

    def test_unknown_slug_returns_404_game_not_found(self):
        r = self._get("does-not-exist")
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertEqual(body["error"]["code"], "GAME_NOT_FOUND")
        self.assertIn("error", body)

    # -- D. hidden / unlisted Game ------------------------------------------

    def test_draft_game_is_404(self):
        _game(slug="draft-game", listing_status="draft")
        r = self._get("draft-game")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"]["code"], "GAME_NOT_FOUND")

    def test_archived_game_is_404(self):
        _game(slug="archived-game", listing_status="archived")
        r = self._get("archived-game")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"]["code"], "GAME_NOT_FOUND")

    # -- E. non-game content ------------------------------------------------

    def test_non_game_content_is_404(self):
        for content_type in ("dlc", "demo", "software", "soundtrack", "unknown"):
            _game(slug=f"{content_type}-slug", content_type=content_type)
            r = self._get(f"{content_type}-slug")
            self.assertEqual(r.status_code, 404, content_type)
            self.assertEqual(r.json()["error"]["code"], "GAME_NOT_FOUND")

    # -- F. no classification -----------------------------------------------

    def test_public_game_without_classification_has_null_classification(self):
        _game(slug="no-classification")
        r = self._get("no-classification")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["classification"])

    # -- G. provisional result ----------------------------------------------

    def test_provisional_result_returns_scores_and_confidence(self):
        game = _game(slug="provisional-game")
        _snapshot(
            game,
            regime="provisional",
            status="READY",
            unified_integer_challenge=[50, 30, 20],
            unified_integer_reward=[20, 30, 50],
            confidence_final="86.42",
            confidence_label="High",
            validated_count=11,
        )
        r = self._get("provisional-game")

        self.assertEqual(r.status_code, 200)
        classification = r.json()["classification"]
        self.assertEqual(classification["status"], "READY")
        self.assertEqual(classification["regime"], "provisional")
        self.assertEqual(
            classification["challenge"], {"micro": 50, "macro": 30, "mystiko": 20}
        )
        self.assertEqual(
            classification["reward"], {"micro": 20, "macro": 30, "mystiko": 50}
        )
        self.assertEqual(classification["confidence_level"], 86.42)
        self.assertEqual(classification["confidence_label"], "High")
        self.assertEqual(classification["submission_count"], 11)
        self.assertFalse(classification["is_stale"])

    # -- H. unified/full result ---------------------------------------------

    def test_unified_result_returns_scores_and_confidence(self):
        game = _game(slug="unified-game")
        _snapshot(
            game,
            regime="unified",
            status="READY",
            unified_integer_challenge=[40, 35, 25],
            unified_integer_reward=[15, 45, 40],
            confidence_final="72.10",
            confidence_label="Medium",
            validated_count=42,
        )
        r = self._get("unified-game")

        self.assertEqual(r.status_code, 200)
        classification = r.json()["classification"]
        self.assertEqual(classification["status"], "READY")
        self.assertEqual(classification["regime"], "unified")
        self.assertEqual(
            classification["challenge"], {"micro": 40, "macro": 35, "mystiko": 25}
        )
        self.assertEqual(classification["confidence_level"], 72.1)
        self.assertEqual(classification["submission_count"], 42)

    # -- I. legitimate non-ready result -------------------------------------

    def test_non_ready_result_has_null_scores_not_zero(self):
        game = _game(slug="non-ready-game")
        _snapshot(game, regime="none", status="NO_SUBMISSIONS", validated_count=0)
        r = self._get("non-ready-game")

        self.assertEqual(r.status_code, 200)
        classification = r.json()["classification"]
        self.assertEqual(classification["status"], "NO_SUBMISSIONS")
        self.assertIsNone(classification["challenge"])
        self.assertIsNone(classification["reward"])
        self.assertIsNone(classification["confidence_level"])

    # -- J. canonical component mapping (asymmetric) ------------------------

    def test_component_mapping_is_micro_macro_mystiko(self):
        game = _game(slug="component-game")
        _snapshot(
            game,
            unified_integer_challenge=[51, 31, 18],
            unified_integer_reward=[18, 51, 31],
        )
        r = self._get("component-game")

        classification = r.json()["classification"]
        self.assertEqual(
            classification["challenge"], {"micro": 51, "macro": 31, "mystiko": 18}
        )
        self.assertEqual(
            classification["reward"], {"micro": 18, "macro": 51, "mystiko": 31}
        )

    # -- K. display-image fallback ------------------------------------------

    def test_display_image_falls_back_to_steam_when_manual_absent(self):
        _game(
            slug="image-game",
            source_type=SourceType.STEAM,
            external_id="730",
            manual_image_url="",
            steam_image_url="https://example.com/steam.jpg",
        )
        r = self._get("image-game")
        self.assertEqual(r.json()["game"]["image_url"], "https://example.com/steam.jpg")

    def test_steam_game_exposes_library_asset_urls(self):
        _game(
            slug="layered-game",
            source_type=SourceType.STEAM,
            external_id="620",
            library_hero_url="https://cdn.cloudflare.steamstatic.com/steam/apps/620/library_hero.jpg",
            library_capsule_url="https://cdn.cloudflare.steamstatic.com/steam/apps/620/library_600x900.jpg",
        )
        r = self._get("layered-game")

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json()["game"]["library_hero_url"],
            "https://cdn.cloudflare.steamstatic.com/steam/apps/620/library_hero.jpg",
        )
        self.assertEqual(
            r.json()["game"]["library_capsule_url"],
            "https://cdn.cloudflare.steamstatic.com/steam/apps/620/library_600x900.jpg",
        )

    def test_manual_game_has_null_library_asset_urls(self):
        _game(slug="manual-no-library", source_type=SourceType.MANUAL, external_id=None)
        r = self._get("manual-no-library")

        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json()["game"]["library_hero_url"])
        self.assertIsNone(r.json()["game"]["library_capsule_url"])

    # -- L + M. no side effects ---------------------------------------------

    def test_get_does_not_contact_steam_or_recalculate(self):
        game = _game(
            slug="side-effect-free", source_type=SourceType.STEAM, external_id="730"
        )
        _snapshot(
            game,
            unified_integer_challenge=[50, 30, 20],
            unified_integer_reward=[20, 30, 50],
        )

        with (
            patch("games.api._build_steam_refresh_service") as refresh_factory,
            patch("games.api._build_steam_import_service") as import_factory,
            patch(
                "classifications.services.calculations.run_game_calculation"
            ) as recalc,
        ):
            r = self._get("side-effect-free")

        self.assertEqual(r.status_code, 200)
        refresh_factory.assert_not_called()
        import_factory.assert_not_called()
        recalc.assert_not_called()

    # -- N. OpenAPI ---------------------------------------------------------

    def test_openapi_declares_game_detail(self):
        r = Client().get("/api/v1/openapi.json")
        self.assertEqual(r.status_code, 200)
        schema = r.json()
        paths = schema["paths"]
        self.assertIn("/api/v1/games/{slug}", paths)
        operation = paths["/api/v1/games/{slug}"]["get"]
        self.assertEqual(operation["operationId"], "game_detail")
        schemas = schema["components"]["schemas"]
        self.assertIn("GameDetailResponse", schemas)
        self.assertIn("PublicGameDetail", schemas)
        self.assertIn("PublicFinalClassification", schemas)
        response_keys = set(operation["responses"].keys())
        self.assertIn("200", response_keys)
        self.assertIn("404", response_keys)
