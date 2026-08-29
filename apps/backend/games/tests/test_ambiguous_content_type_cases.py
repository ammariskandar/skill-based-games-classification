"""
Ambiguous content-type & exclusion edge cases — SBGC-98.

The closing edge-case suite for the SBGC-14 exclusion epic: ambiguous Steam
type strings and malformed payloads, the standalone-expansion override
lifecycle, upstream Steam type drift (with and without overrides), resume-sync
reversion, and GOTY/bundle public-boundary behavior.  No network calls — the
Steam adapter path is exercised with raw payload dicts and refresh uses a
mocked foundation.
"""

from __future__ import annotations

from unittest import mock

from classifications.models import CalculationEpoch, ClassificationSnapshot
from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.imports.steam import (
    SteamGamePersistenceService,
    SteamGameRefreshService,
    SteamGameRefreshStatus,
)
from games.services.steam.adapters.app_details import SteamAppDetailsAdapter
from games.services.steam.dto import (
    LookupStatus,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)
from games.services.steam.import_foundation import SteamImportFoundation
from games.services.steam.mapping import map_steam_product_type

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _game(slug: str, **kwargs) -> Game:
    defaults = dict(
        name=slug.replace("-", " ").title(),
        slug=slug,
        source_type=SourceType.STEAM,
        external_id="730",
        content_type=ContentType.GAME,
        listing_status=ListingStatus.PUBLISHED,
    )
    defaults.update(kwargs)
    return Game.objects.create(**defaults)


def _epoch() -> CalculationEpoch:
    epoch, _ = CalculationEpoch.objects.get_or_create(
        epoch_id="ambiguous-cases-epoch",
        defaults={
            "cutoff_at": timezone.now(),
            "master_version": "STATISTICAL_MODEL_V1.0.0",
        },
    )
    return epoch


def _ready_snapshot(game: Game, **kwargs) -> ClassificationSnapshot:
    """A current READY published classification (the API read boundary)."""
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
        unified_integer_challenge=[51, 31, 18],
        unified_integer_reward=[17, 29, 54],
    )
    defaults.update(kwargs)
    return ClassificationSnapshot.objects.create(game=game, **defaults)


def _steam_change_data(**overrides) -> dict:
    data = {
        "source_type": SourceType.STEAM,
        "external_id": "730",
        "name": "Dishonored: Death of the Outsider",
        "slug": "dishonored-death-of-the-outsider",
        "content_type": ContentType.GAME,
        "listing_status": ListingStatus.PUBLISHED,
        "release_date": "",
        "developer": "",
        "description": "",
        "manual_image_url": "",
        "manual_website_url": "",
        "_changelist_filters": "",
    }
    data.update(overrides)
    return data


def _refresh_lookup(
    app_id: str = "730",
    name: str = "Dishonored: Death of the Outsider",
    content_type: str = "game",
) -> SteamAppLookupResult:
    candidate = SteamGameImportCandidate(
        app_id=app_id,
        name=name,
        content_type=content_type,
    )
    return SteamAppLookupResult(
        status=LookupStatus.FOUND,
        app_id=app_id,
        candidate=candidate,
    )


def _refresh_service(foundation):
    return SteamGameRefreshService(foundation, SteamGamePersistenceService())


def _adapter_details(payload_data: dict) -> object:
    """Run one raw Steam ``data`` dict through the real adapter parse path."""
    adapter = SteamAppDetailsAdapter(mock.MagicMock())
    return adapter._parse_response(
        "730", {"730": {"success": True, "data": payload_data}}
    )  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# Class 1: ambiguous Steam type strings
# ---------------------------------------------------------------------------


class AmbiguousSteamTypeMappingTests(SimpleTestCase):
    """Raw product-type strings resolve deterministically (SBGC-95/98)."""

    def test_whitespace_and_casing_tolerance(self):
        cases = {
            " GAME ": ContentType.GAME,
            "Dlc": ContentType.DLC,
            "SoFtWaRe": ContentType.SOFTWARE,
            " MUSIC ": ContentType.SOUNDTRACK,
            "SoundTrack": ContentType.SOUNDTRACK,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(map_steam_product_type(raw), expected)

    def test_unrecognized_steam_product_types_fallback_to_unknown(self):
        for raw in (
            "mod",
            "tool",
            "hardware",
            "video",
            "series",
            "episode",
            "advertising",
            "application",
            "bundle",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(map_steam_product_type(raw), ContentType.UNKNOWN)

    def test_malformed_type_payloads_fallback_to_unknown(self):
        for raw_type in ("", "   ", None, 999, {}, []):
            with self.subTest(raw_type=repr(raw_type)):
                details = _adapter_details({"name": "Ambiguous", "type": raw_type})
                self.assertEqual(details.content_type, ContentType.UNKNOWN)

    def test_missing_type_key_fallback_to_unknown(self):
        details = _adapter_details({"name": "Ambiguous"})
        self.assertEqual(details.content_type, ContentType.UNKNOWN)


# ---------------------------------------------------------------------------
# Class 2: standalone-expansion lifecycle
# ---------------------------------------------------------------------------


class StandaloneExpansionLifecycleTests(TestCase):
    """DLC ingested → owner override to GAME → refresh preserves it."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(username="editor", password="p")
        # Ingested as DLC (Steam reports standalone expansions as type=dlc).
        cls.game = _game(
            "dishonored-death-of-the-outsider",
            name="Dishonored: Death of the Outsider",
            content_type=ContentType.DLC,
        )
        _ready_snapshot(cls.game)

    def setUp(self):
        self.client.force_login(self.user)

    def test_dlc_to_game_override_flow(self):
        # Ingested state: DLC, never overridden, excluded everywhere.
        self.assertFalse(self.game.content_type_overridden)
        self.assertNotIn(self.game, Game.objects.publicly_listable())
        self.assertEqual(
            Client().get("/api/v1/games/dishonored-death-of-the-outsider").status_code,
            404,
        )

        # Admin override: DLC → GAME (already PUBLISHED).
        url = reverse("admin:games_game_change", args=(self.game.pk,))
        response = self.client.post(
            url, _steam_change_data(content_type=ContentType.GAME)
        )
        self.assertEqual(response.status_code, 302)

        self.game.refresh_from_db()
        self.assertEqual(self.game.content_type, ContentType.GAME)
        self.assertTrue(self.game.content_type_overridden)
        self.assertIn(self.game, Game.objects.publicly_listable())

        # Visible across the public read surfaces.
        detail = Client().get("/api/v1/games/dishonored-death-of-the-outsider")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.json()["game"]["slug"], "dishonored-death-of-the-outsider"
        )
        catalogue = Client().get("/api/v1/games/").json()
        self.assertIn(
            "dishonored-death-of-the-outsider",
            [g["slug"] for g in catalogue["results"]],
        )
        search = Client().get("/api/v1/games/search-index").json()
        self.assertIn(
            "dishonored-death-of-the-outsider",
            [g["slug"] for g in search["games"]],
        )

    def test_override_persists_across_repeated_refresh(self):
        self.game.content_type = ContentType.GAME
        self.game.content_type_overridden = True
        self.game.save()

        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = _refresh_lookup(content_type="dlc")
        service = _refresh_service(foundation)

        for _ in range(2):
            result = service.refresh(self.game)
            self.assertEqual(result.status, SteamGameRefreshStatus.UNCHANGED)
            self.game.refresh_from_db()
            self.assertEqual(self.game.content_type, ContentType.GAME)
            self.assertIn(self.game, Game.objects.publicly_listable())


# ---------------------------------------------------------------------------
# Class 3: upstream metadata drift
# ---------------------------------------------------------------------------


class UpstreamMetadataDriftTests(TestCase):
    """Steam type changes: apply when unoverridden, preserve when overridden."""

    def _drift_lookup(self, content_type: str, app_id: str, name: str):
        return _refresh_lookup(app_id=app_id, name=name, content_type=content_type)

    def test_upstream_type_drift_revokes_listing_when_unoverridden(self):
        game = _game("portal-2", name="Portal 2", external_id="620")
        _ready_snapshot(game)
        self.assertIn(game, Game.objects.publicly_listable())

        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = self._drift_lookup(
            "software", "620", "Portal 2"
        )
        result = _refresh_service(foundation).refresh(game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        game.refresh_from_db()
        self.assertEqual(game.content_type, ContentType.SOFTWARE)
        self.assertNotIn(game, Game.objects.publicly_listable())
        self.assertEqual(Client().get("/api/v1/games/portal-2").status_code, 404)
        self.assertEqual(Client().get("/api/v1/games/").json()["count"], 0)
        self.assertEqual(Client().get("/api/v1/rankings/").json()["count"], 0)
        self.assertEqual(Client().get("/api/v1/games/search-index").json()["games"], [])

    def test_upstream_type_drift_preserves_listing_when_overridden(self):
        game = _game("portal-2", name="Portal 2", external_id="620")
        game.content_type_overridden = True
        game.save()
        self.assertIn(game, Game.objects.publicly_listable())

        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = self._drift_lookup(
            "dlc", "620", "Portal 2"
        )
        result = _refresh_service(foundation).refresh(game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UNCHANGED)
        game.refresh_from_db()
        self.assertEqual(game.content_type, ContentType.GAME)
        self.assertTrue(game.content_type_overridden)
        self.assertIn(game, Game.objects.publicly_listable())

    def test_resume_sync_allows_upstream_drift_to_revert_classification(self):
        user = User.objects.create_superuser(username="editor", password="p")
        game = _game("portal-2", name="Portal 2", external_id="620")
        game.content_type = ContentType.GAME
        game.content_type_overridden = True
        game.save()
        self.assertIn(game, Game.objects.publicly_listable())

        # Operator clears the override via the Admin resume control.
        self.client.force_login(user)
        url = reverse("admin:games_game_change", args=(game.pk,))
        data = {
            "source_type": SourceType.STEAM,
            "external_id": "620",
            "name": "Portal 2",
            "slug": "portal-2",
            "content_type": ContentType.GAME,
            "listing_status": ListingStatus.PUBLISHED,
            "release_date": "",
            "developer": "",
            "description": "",
            "manual_image_url": "",
            "manual_website_url": "",
            "resume_content_type": "on",
            "_changelist_filters": "",
        }
        self.client.post(url, data)
        game.refresh_from_db()
        self.assertFalse(game.content_type_overridden)

        # Next refresh re-applies upstream drift and evicts the record.
        foundation = mock.MagicMock(spec=SteamImportFoundation)
        foundation.prepare_candidate.return_value = self._drift_lookup(
            "dlc", "620", "Portal 2"
        )
        result = _refresh_service(foundation).refresh(game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        game.refresh_from_db()
        self.assertEqual(game.content_type, ContentType.DLC)
        self.assertNotIn(game, Game.objects.publicly_listable())
        self.assertEqual(Client().get("/api/v1/games/portal-2").status_code, 404)


# ---------------------------------------------------------------------------
# Class 4: ambiguous-product public boundary
# ---------------------------------------------------------------------------


class AmbiguousProductPublicBoundaryTests(TestCase):
    """Unknown types never leak; GOTY base clients stay listable."""

    def test_unknown_type_with_ready_snapshot_never_leaks(self):
        unknown = _game("mystery-utility", content_type=ContentType.UNKNOWN)
        _ready_snapshot(unknown)

        self.assertEqual(Client().get("/api/v1/games/").json()["count"], 0)
        self.assertEqual(Client().get("/api/v1/rankings/").json()["count"], 0)
        self.assertEqual(Client().get("/api/v1/games/search-index").json()["games"], [])
        self.assertEqual(Client().get("/api/v1/games/mystery-utility").status_code, 404)

    def test_deluxe_edition_game_with_dlc_metadata_remains_listable(self):
        # A GOTY/Deluxe release is classified GAME because it ships the base
        # client; bundled-DLC wording does not affect content_type.
        deluxe = _game(
            "xcom-2-war-of-the-chosen-collection",
            name="XCOM 2: War of the Chosen Collection",
        )
        _ready_snapshot(deluxe)

        self.assertIn(deluxe, Game.objects.publicly_listable())
        catalogue = Client().get("/api/v1/games/").json()
        self.assertIn(deluxe.slug, [g["slug"] for g in catalogue["results"]])
        search = Client().get("/api/v1/games/search-index").json()
        self.assertIn(deluxe.slug, [g["slug"] for g in search["games"]])

    def test_soundtrack_bundle_remains_excluded_from_search_and_rankings(self):
        soundtrack = _game(
            "official-soundtrack-bundle", content_type=ContentType.SOUNDTRACK
        )
        _ready_snapshot(soundtrack)

        self.assertEqual(Client().get("/api/v1/games/?q=Soundtrack").json()["count"], 0)
        self.assertEqual(Client().get("/api/v1/rankings/").json()["count"], 0)
        self.assertNotIn(soundtrack, Game.objects.publicly_listable())
