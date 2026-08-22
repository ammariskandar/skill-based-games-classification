"""
Steam metadata refresh service tests — SBGC-56.

Covers eligibility, updated/unchanged/unavailable outcomes, identity
invariants, error propagation, preservation, type-transition listing
behavior, timestamp stability, and the network-outside-transaction
boundary.
"""

from __future__ import annotations

from datetime import date
from unittest import mock

from classifications.models import EditorialClassification
from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from games.models import Game, ListingStatus, SourceType
from games.services.imports.steam import (
    SteamGamePersistenceService,
    SteamGameRefreshResult,
    SteamGameRefreshService,
    SteamGameRefreshStatus,
    SteamRefreshError,
)
from games.services.steam.adapters import SteamMalformedPayloadError
from games.services.steam.dto import (
    LookupStatus,
    SteamAppLookupResult,
    SteamGameImportCandidate,
)
from games.services.steam.errors import SteamTimeoutError
from games.services.steam.import_foundation import SteamImportFoundation
from games.services.steam.library_assets import build_steam_library_asset_urls


def _library_urls(content_type: str, external_id: str) -> tuple[str, str]:
    """Derived Library Hero/Capsule URLs matching the persistence mapping."""
    if content_type != "game":
        return "", ""
    return build_steam_library_asset_urls(external_id)


def _candidate(
    app_id: str = "620",
    name: str = "Portal 2",
    content_type: str = "game",
    header_image_url: str | None = None,
    description: str | None = None,
    developer: str | None = None,
    release_date: date | None = None,
) -> SteamGameImportCandidate:
    return SteamGameImportCandidate(
        app_id=app_id,
        name=name,
        content_type=content_type,
        header_image_url=header_image_url,
        description=description,
        developer=developer,
        release_date=release_date,
    )


def _found_lookup(
    app_id: str = "620",
    name: str = "Portal 2",
    content_type: str = "game",
    header_image_url: str | None = None,
    description: str | None = None,
    developer: str | None = None,
    release_date: date | None = None,
) -> SteamAppLookupResult:
    return SteamAppLookupResult(
        status=LookupStatus.FOUND,
        app_id=app_id,
        candidate=_candidate(
            app_id,
            name,
            content_type,
            header_image_url,
            description,
            developer,
            release_date,
        ),
    )


def _unavailable_lookup(app_id: str = "620") -> SteamAppLookupResult:
    return SteamAppLookupResult(status=LookupStatus.UNAVAILABLE, app_id=app_id)


def _steam_game(
    external_id: str = "620",
    name: str = "Portal 2",
    content_type: str = "game",
    **kwargs,
) -> Game:
    hero, capsule = _library_urls(content_type, external_id)
    kwargs.setdefault("library_hero_url", hero)
    kwargs.setdefault("library_capsule_url", capsule)
    return Game.objects.create(
        source_type=SourceType.STEAM,
        external_id=external_id,
        name=name,
        slug=f"game-{external_id}",
        content_type=content_type,
        **kwargs,
    )


def _make_service():
    foundation = mock.MagicMock(spec=SteamImportFoundation)
    persistence = SteamGamePersistenceService()
    return SteamGameRefreshService(foundation, persistence), foundation


# ---------------------------------------------------------------------------
# Result invariants
# ---------------------------------------------------------------------------


class RefreshResultInvariantTests(SimpleTestCase):
    def test_updated_requires_changed_fields(self):
        with self.assertRaises(ValueError):
            SteamGameRefreshResult(status=SteamGameRefreshStatus.UPDATED, game_id=1)

    def test_unchanged_rejects_changed_fields(self):
        with self.assertRaises(ValueError):
            SteamGameRefreshResult(
                status=SteamGameRefreshStatus.UNCHANGED,
                game_id=1,
                changed_fields=("name",),
            )

    def test_unavailable_rejects_changed_fields(self):
        with self.assertRaises(ValueError):
            SteamGameRefreshResult(
                status=SteamGameRefreshStatus.UNAVAILABLE,
                game_id=1,
                changed_fields=("name",),
            )

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            SteamGameRefreshResult(
                status=SteamGameRefreshStatus.UPDATED,
                game_id=1,
                changed_fields=("slug",),
            )

    def test_non_string_field_rejected(self):
        with self.assertRaises(TypeError):
            SteamGameRefreshResult(
                status=SteamGameRefreshStatus.UPDATED,
                game_id=1,
                changed_fields=(1,),  # type: ignore[arg-type]
            )

    def test_boolean_game_id_rejected(self):
        with self.assertRaises(TypeError):
            SteamGameRefreshResult(  # type: ignore[arg-type]
                status=SteamGameRefreshStatus.UNCHANGED,
                game_id=True,
            )

    def test_non_enum_status_rejected(self):
        with self.assertRaises(TypeError):
            SteamGameRefreshResult(
                status="updated",  # type: ignore[arg-type]
                game_id=1,
            )

    def test_valid_updated_result(self):
        result = SteamGameRefreshResult(
            status=SteamGameRefreshStatus.UPDATED,
            game_id=7,
            changed_fields=("name", "steam_image_url"),
        )
        self.assertEqual(result.game_id, 7)
        self.assertEqual(result.changed_fields, ("name", "steam_image_url"))

    def test_valid_unavailable_result(self):
        result = SteamGameRefreshResult(
            status=SteamGameRefreshStatus.UNAVAILABLE,
            game_id=7,
        )
        self.assertEqual(result.changed_fields, ())


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------


class RefreshEligibilityTests(TestCase):
    def setUp(self):
        self.service, self.foundation = _make_service()

    def test_manual_game_raises_without_network(self):
        manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Chess",
            slug="chess",
        )

        with self.assertRaises(SteamRefreshError):
            self.service.refresh(manual)

        self.foundation.prepare_candidate.assert_not_called()
        manual.refresh_from_db()
        self.assertIsNone(manual.last_steam_refresh_at)

    def test_unsaved_game_raises_without_network(self):
        unsaved = Game(
            source_type=SourceType.STEAM,
            external_id="620",
            name="Unsaved",
            slug="unsaved",
        )

        with self.assertRaises(SteamRefreshError):
            self.service.refresh(unsaved)

        self.foundation.prepare_candidate.assert_not_called()

    def test_invalid_stored_external_id_raises_without_network(self):
        game = _steam_game(external_id="abc", name="Bad ID")

        with self.assertRaises(SteamRefreshError):
            self.service.refresh(game)

        self.foundation.prepare_candidate.assert_not_called()

    def test_non_game_instance_rejected(self):
        with self.assertRaises(TypeError):
            self.service.refresh("not-a-game")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------


class RefreshOutcomeTests(TestCase):
    def setUp(self):
        self.service, self.foundation = _make_service()
        self.game = _steam_game(external_id="620", name="Portal 2")

    def test_updated_name(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            name="Portal 2 — Reloaded"
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.assertEqual(result.changed_fields, ("name",))
        self.game.refresh_from_db()
        self.assertEqual(self.game.name, "Portal 2 — Reloaded")
        self.assertIsNotNone(self.game.last_steam_refresh_at)

    def test_updated_content_type(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            content_type="dlc"
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.assertEqual(
            result.changed_fields,
            ("content_type", "library_hero_url", "library_capsule_url"),
        )
        self.game.refresh_from_db()
        self.assertEqual(self.game.content_type, "dlc")
        # Non-game Steam content has no Library Hero/Capsule presentation.
        self.assertEqual(self.game.library_hero_url, "")
        self.assertEqual(self.game.library_capsule_url, "")

    def test_updated_image(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            header_image_url="https://cdn.example.com/new.jpg"
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.assertEqual(result.changed_fields, ("steam_image_url",))
        self.game.refresh_from_db()
        self.assertEqual(self.game.steam_image_url, "https://cdn.example.com/new.jpg")

    def test_transition_to_game_populates_library_assets(self):
        dlc = _steam_game(external_id="730", name="Counter-Strike", content_type="dlc")
        hero, capsule = build_steam_library_asset_urls("730")
        self.foundation.prepare_candidate.return_value = _found_lookup(
            app_id="730",
            name="Counter-Strike",
            content_type="game",
        )

        result = self.service.refresh(dlc)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.assertEqual(
            result.changed_fields,
            ("content_type", "library_hero_url", "library_capsule_url"),
        )
        dlc.refresh_from_db()
        self.assertEqual(dlc.content_type, "game")
        self.assertEqual(dlc.library_hero_url, hero)
        self.assertEqual(dlc.library_capsule_url, capsule)

    def test_library_assets_unchanged_for_game_content_type(self):
        hero, capsule = build_steam_library_asset_urls("620")
        self.assertEqual(self.game.library_hero_url, hero)
        self.assertEqual(self.game.library_capsule_url, capsule)

        self.foundation.prepare_candidate.return_value = _found_lookup()

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UNCHANGED)
        self.assertEqual(result.changed_fields, ())

    def test_changed_fields_deterministic_order(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            name="Portal 2 — Reloaded",
            content_type="unknown",
            header_image_url="https://cdn.example.com/new.jpg",
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.assertEqual(
            result.changed_fields,
            (
                "name",
                "content_type",
                "steam_image_url",
                "library_hero_url",
                "library_capsule_url",
            ),
        )

    def test_unchanged(self):
        self.foundation.prepare_candidate.return_value = _found_lookup()
        original_updated_at = self.game.updated_at

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UNCHANGED)
        self.assertEqual(result.changed_fields, ())
        self.game.refresh_from_db()
        # No model save — updated_at stays untouched …
        self.assertEqual(self.game.updated_at, original_updated_at)
        # … but the successful verification is still recorded.
        self.assertIsNotNone(self.game.last_steam_refresh_at)

    def test_unavailable_preserves_completely(self):
        self.foundation.prepare_candidate.return_value = _unavailable_lookup("620")
        original_updated_at = self.game.updated_at

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UNAVAILABLE)
        self.assertEqual(result.game_id, self.game.pk)
        self.assertEqual(result.changed_fields, ())
        self.game.refresh_from_db()
        self.assertEqual(self.game.name, "Portal 2")
        self.assertEqual(self.game.updated_at, original_updated_at)
        self.assertIsNone(self.game.last_steam_refresh_at)


# ---------------------------------------------------------------------------
# Identity invariant
# ---------------------------------------------------------------------------


class RefreshIdentityTests(TestCase):
    def setUp(self):
        self.service, self.foundation = _make_service()
        self.game = _steam_game(external_id="620", name="Portal 2")

    def test_lookup_app_id_mismatch_raises_without_writes(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            app_id="999", name="Other Game"
        )

        with self.assertRaises(SteamRefreshError):
            self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.name, "Portal 2")
        self.assertIsNone(self.game.last_steam_refresh_at)

    def test_candidate_app_id_mismatch_raises_without_writes(self):
        lookup = SteamAppLookupResult(
            status=LookupStatus.FOUND,
            app_id="620",
            candidate=_candidate(app_id="999", name="Other Game"),
        )
        self.foundation.prepare_candidate.return_value = lookup

        with self.assertRaises(SteamRefreshError):
            self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.name, "Portal 2")
        self.assertIsNone(self.game.last_steam_refresh_at)

    def test_source_and_external_id_never_mutated(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(name="Changed")

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.source_type, SourceType.STEAM)
        self.assertEqual(self.game.external_id, "620")


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class RefreshErrorTests(TestCase):
    def setUp(self):
        self.service, self.foundation = _make_service()
        self.game = _steam_game(external_id="620", name="Portal 2")

    def test_transport_error_propagates_without_writes(self):
        self.foundation.prepare_candidate.side_effect = SteamTimeoutError("timeout")

        with self.assertRaises(SteamTimeoutError):
            self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertIsNone(self.game.last_steam_refresh_at)
        self.assertEqual(self.game.name, "Portal 2")

    def test_malformed_payload_propagates_without_writes(self):
        self.foundation.prepare_candidate.side_effect = SteamMalformedPayloadError(
            "bad"
        )

        with self.assertRaises(SteamMalformedPayloadError):
            self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertIsNone(self.game.last_steam_refresh_at)

    def test_malformed_candidate_image_raises_before_transaction(self):
        lookup = SteamAppLookupResult(
            status=LookupStatus.FOUND,
            app_id="620",
            candidate=_candidate(header_image_url="http://cdn.example.com/x.jpg"),
        )
        self.foundation.prepare_candidate.return_value = lookup

        with self.assertRaises(SteamMalformedPayloadError):
            self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.steam_image_url, "")
        self.assertIsNone(self.game.last_steam_refresh_at)


# ---------------------------------------------------------------------------
# Preservation and listing behavior
# ---------------------------------------------------------------------------


class RefreshPreservationTests(TestCase):
    def setUp(self):
        self.service, self.foundation = _make_service()
        self.game = _steam_game(
            external_id="620",
            name="Portal 2",
            listing_status=ListingStatus.PUBLISHED,
            description="Editorial description.",
            manual_image_url="https://cdn.example.com/manual.png",
            manual_website_url="https://example.com",
        )

    def test_refresh_preserves_slug_listing_and_manual_metadata(self):
        original_slug = self.game.slug
        self.foundation.prepare_candidate.return_value = _found_lookup(
            name="Portal 2 — Reloaded",
            header_image_url="https://cdn.example.com/new.jpg",
        )

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.slug, original_slug)
        self.assertEqual(self.game.listing_status, ListingStatus.PUBLISHED)
        self.assertEqual(self.game.description, "Editorial description.")
        self.assertEqual(
            self.game.manual_image_url, "https://cdn.example.com/manual.png"
        )
        self.assertEqual(self.game.manual_website_url, "https://example.com")

    def test_refresh_preserves_classification(self):
        editor = User.objects.create_user(username="refresh-editor")
        set_editorial_classification(
            game=self.game,
            updated_by=editor,
            challenge=ScoreDistribution(50, 20, 30),
            reward=ScoreDistribution(10, 30, 60),
            notes="Keep me.",
        )
        self.foundation.prepare_candidate.return_value = _found_lookup(name="Reloaded")

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        classification = EditorialClassification.objects.get(game=self.game)
        self.assertEqual(classification.notes, "Keep me.")
        self.assertEqual(classification.challenge_profile.micro_score, 50)
        self.assertEqual(classification.reward_profile.macro_score, 60)

    def test_type_transition_excludes_from_listing(self):
        """Published GAME → DLC keeps Published but leaves public listing."""
        self.foundation.prepare_candidate.return_value = _found_lookup(
            content_type="dlc"
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.game.refresh_from_db()
        self.assertEqual(self.game.content_type, "dlc")
        self.assertEqual(self.game.listing_status, ListingStatus.PUBLISHED)
        self.assertFalse(
            Game.objects.publicly_listable().filter(pk=self.game.pk).exists()
        )

    def test_type_transition_to_unknown_excludes_from_listing(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            content_type="unknown"
        )

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.listing_status, ListingStatus.PUBLISHED)
        self.assertFalse(
            Game.objects.publicly_listable().filter(pk=self.game.pk).exists()
        )


# ---------------------------------------------------------------------------
# Transaction boundary
# ---------------------------------------------------------------------------


class RefreshTransactionBoundaryTests(TransactionTestCase):
    def test_network_preparation_outside_transaction(self):
        game = _steam_game(external_id="620", name="Portal 2")
        service = SteamGameRefreshService(
            foundation=mock.MagicMock(spec=SteamImportFoundation),
            persistence=SteamGamePersistenceService(),
        )
        observed: list[bool] = []

        def guarded_prepare(app_id: str):
            observed.append(connection.in_atomic_block)
            return _found_lookup(name="Portal 2 — Reloaded")

        with mock.patch.object(
            service._foundation, "prepare_candidate", side_effect=guarded_prepare
        ):
            result = service.refresh(game)

        self.assertEqual(observed, [False])
        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        game.refresh_from_db()
        self.assertEqual(game.name, "Portal 2 — Reloaded")


# ---------------------------------------------------------------------------
# Editable metadata ownership (SBGC-188)
# ---------------------------------------------------------------------------


class EditableMetadataRefreshTests(TestCase):
    def setUp(self):
        self.service, self.foundation = _make_service()
        self.game = _steam_game(
            external_id="620",
            name="Portal 2",
            description="A",
            developer="B",
            release_date=date(2011, 1, 1),
        )

    def test_steam_managed_fields_update(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            description="D",
            developer="E",
            release_date=date(2012, 2, 2),
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "D")
        self.assertEqual(self.game.developer, "E")
        self.assertEqual(self.game.release_date, date(2012, 2, 2))

    def test_description_override_preserved(self):
        self.game.description = "Human"
        self.game.description_overridden = True
        self.game.save()

        self.foundation.prepare_candidate.return_value = _found_lookup(
            description="New Steam description",
            developer="New Steam developer",
            release_date=date(2013, 3, 3),
        )

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "Human")
        self.assertEqual(self.game.developer, "New Steam developer")
        self.assertEqual(self.game.release_date, date(2013, 3, 3))
        self.assertTrue(self.game.description_overridden)
        self.assertFalse(self.game.developer_overridden)
        self.assertFalse(self.game.release_date_overridden)

    def test_developer_override_only(self):
        self.game.developer = "Human Studio"
        self.game.developer_overridden = True
        self.game.save()

        self.foundation.prepare_candidate.return_value = _found_lookup(
            description="D2", developer="Steam Studio", release_date=date(2014, 4, 4)
        )

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "D2")
        self.assertEqual(self.game.developer, "Human Studio")
        self.assertEqual(self.game.release_date, date(2014, 4, 4))

    def test_release_date_override_only(self):
        self.game.release_date = date(2000, 1, 1)
        self.game.release_date_overridden = True
        self.game.save()

        self.foundation.prepare_candidate.return_value = _found_lookup(
            description="D3", developer="E3", release_date=date(2015, 5, 5)
        )

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "D3")
        self.assertEqual(self.game.developer, "E3")
        self.assertEqual(self.game.release_date, date(2000, 1, 1))

    def test_multiple_overrides(self):
        self.game.description = "Human desc"
        self.game.description_overridden = True
        self.game.developer = "Human dev"
        self.game.developer_overridden = True
        self.game.save()

        self.foundation.prepare_candidate.return_value = _found_lookup(
            description="S desc", developer="S dev", release_date=date(2016, 6, 6)
        )

        self.service.refresh(self.game)

        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "Human desc")
        self.assertEqual(self.game.developer, "Human dev")
        self.assertEqual(self.game.release_date, date(2016, 6, 6))

    def test_missing_upstream_value_preserves(self):
        self.foundation.prepare_candidate.return_value = _found_lookup(
            description=None, developer=None, release_date=None
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UNCHANGED)
        self.game.refresh_from_db()
        self.assertEqual(self.game.description, "A")
        self.assertEqual(self.game.developer, "B")
        self.assertEqual(self.game.release_date, date(2011, 1, 1))

    def test_resume_sync_repopulates(self):
        self.game.developer = "Human Studio"
        self.game.developer_overridden = True
        self.game.save()

        # Operator clears the override (resume) then a refresh repopulates.
        self.game.developer_overridden = False
        self.game.save(update_fields=["developer_overridden"])

        self.foundation.prepare_candidate.return_value = _found_lookup(
            developer="Current Steam Studio"
        )

        result = self.service.refresh(self.game)

        self.assertEqual(result.status, SteamGameRefreshStatus.UPDATED)
        self.game.refresh_from_db()
        self.assertEqual(self.game.developer, "Current Steam Studio")
        self.assertFalse(self.game.developer_overridden)
