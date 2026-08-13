"""
Steam game persistence service tests — SBGC-54.

Database-backed tests for ``SteamGamePersistenceService``.  No network —
the persistence layer never touches Steam transport.
"""

from __future__ import annotations

from unittest import mock

from classifications.models import EditorialClassification
from classifications.services.editorial import (
    ScoreDistribution,
    set_editorial_classification,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from games.models import Game, ListingStatus, SourceType
from games.services.imports.steam import (
    SteamGameImportResult,
    SteamGameImportStatus,
    SteamGamePersistenceService,
)
from games.services.steam.adapters import SteamMalformedPayloadError
from games.services.steam.dto import SteamAppId, SteamGameImportCandidate


def _candidate(
    app_id: str = "730",
    name: str = "Counter-Strike",
    content_type: str = "game",
    header_image_url: str | None = None,
) -> SteamGameImportCandidate:
    return SteamGameImportCandidate(
        app_id=app_id,
        name=name,
        content_type=content_type,
        header_image_url=header_image_url,
    )


def _result(
    status: SteamGameImportStatus,
    app_id: str = "730",
    game_id: int | None = None,
) -> SteamGameImportResult:
    return SteamGameImportResult(
        status=status,
        app_id=SteamAppId(app_id),
        game_id=game_id,
    )


# ---------------------------------------------------------------------------
# Result invariants
# ---------------------------------------------------------------------------


class ResultInvariantTests(SimpleTestCase):
    def test_created_requires_game_id(self):
        with self.assertRaises(ValueError):
            _result(SteamGameImportStatus.CREATED)

    def test_updated_requires_game_id(self):
        with self.assertRaises(ValueError):
            _result(SteamGameImportStatus.UPDATED)

    def test_unchanged_requires_game_id(self):
        with self.assertRaises(ValueError):
            _result(SteamGameImportStatus.UNCHANGED)

    def test_unavailable_rejects_game_id(self):
        with self.assertRaises(ValueError):
            _result(SteamGameImportStatus.UNAVAILABLE, game_id=1)

    def test_boolean_game_id_rejected(self):
        with self.assertRaises(TypeError):
            _result(SteamGameImportStatus.CREATED, game_id=True)  # type: ignore[arg-type]

    def test_non_int_game_id_rejected(self):
        with self.assertRaises(TypeError):
            _result(SteamGameImportStatus.CREATED, game_id="1")  # type: ignore[arg-type]

    def test_non_enum_status_rejected(self):
        with self.assertRaises(TypeError):
            SteamGameImportResult(
                status="created",  # type: ignore[arg-type]
                app_id=SteamAppId("730"),
                game_id=1,
            )

    def test_non_app_id_type_rejected(self):
        with self.assertRaises(TypeError):
            SteamGameImportResult(
                status=SteamGameImportStatus.CREATED,
                app_id="730",  # type: ignore[arg-type]
                game_id=1,
            )

    def test_valid_created_result(self):
        result = _result(SteamGameImportStatus.CREATED, game_id=5)
        self.assertEqual(result.game_id, 5)
        self.assertEqual(result.app_id.value, "730")

    def test_valid_unavailable_result(self):
        result = _result(SteamGameImportStatus.UNAVAILABLE)
        self.assertIsNone(result.game_id)


# ---------------------------------------------------------------------------
# New imports
# ---------------------------------------------------------------------------


class NewImportTests(TestCase):
    def setUp(self):
        self.service = SteamGamePersistenceService()

    def test_creates_steam_game_with_canonical_fields(self):
        result = self.service.persist(_candidate("620", "Portal 2"))

        self.assertEqual(result.status, SteamGameImportStatus.CREATED)
        self.assertIsNotNone(result.game_id)

        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.source_type, SourceType.STEAM)
        self.assertEqual(game.external_id, "620")
        self.assertEqual(game.name, "Portal 2")
        self.assertEqual(game.content_type, "game")
        self.assertEqual(game.slug, "portal-2")

    def test_new_game_starts_draft(self):
        result = self.service.persist(_candidate("620", "Portal 2"))
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.listing_status, ListingStatus.DRAFT)

    def test_new_game_has_no_manual_metadata(self):
        result = self.service.persist(_candidate("620", "Portal 2"))
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.manual_description, "")
        self.assertEqual(game.manual_image_url, "")
        self.assertEqual(game.manual_website_url, "")

    def test_content_type_persisted_directly(self):
        result = self.service.persist(_candidate("220", "Demo", content_type="demo"))
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.content_type, "demo")

    def test_unknown_content_type_persists(self):
        result = self.service.persist(
            _candidate("9999", "Mystery", content_type="unknown")
        )
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.content_type, "unknown")
        self.assertEqual(game.listing_status, ListingStatus.DRAFT)

    def test_slug_collision_uses_suffixed_slug(self):
        Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Chess",
            slug="chess",
        )
        result = self.service.persist(_candidate("730", "Chess"))
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.slug, "chess-steam-730")

    def test_external_id_and_pk_never_equal(self):
        result = self.service.persist(_candidate("620", "Portal 2"))
        game = Game.objects.get(pk=result.game_id)
        self.assertNotEqual(str(game.pk), game.external_id)


# ---------------------------------------------------------------------------
# Re-import behavior
# ---------------------------------------------------------------------------


class ReimportTests(TestCase):
    def setUp(self):
        self.service = SteamGamePersistenceService()
        created = self.service.persist(_candidate("620", "Portal 2"))
        self.game = Game.objects.get(pk=created.game_id)
        self.original_pk = self.game.pk
        self.original_slug = self.game.slug
        self.original_created_at = self.game.created_at

    def test_identical_candidate_is_unchanged(self):
        result = self.service.persist(_candidate("620", "Portal 2"))

        self.assertEqual(result.status, SteamGameImportStatus.UNCHANGED)
        self.assertEqual(result.game_id, self.original_pk)
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="620"
        )
        self.assertEqual(steam_rows.count(), 1)

    def test_unchanged_does_not_touch_updated_at(self):
        self.service.persist(_candidate("620", "Portal 2"))
        game = Game.objects.get(pk=self.original_pk)
        self.assertEqual(game.updated_at, self.game.updated_at)

    def test_name_refresh_updates_name_and_preserves_slug(self):
        result = self.service.persist(_candidate("620", "Portal 2 — Reloaded"))

        self.assertEqual(result.status, SteamGameImportStatus.UPDATED)
        game = Game.objects.get(pk=self.original_pk)
        self.assertEqual(game.name, "Portal 2 — Reloaded")
        self.assertEqual(game.slug, self.original_slug)
        self.assertEqual(game.pk, self.original_pk)
        self.assertEqual(game.created_at, self.original_created_at)

    def test_content_type_refresh(self):
        result = self.service.persist(
            _candidate("620", "Portal 2", content_type="unknown")
        )

        self.assertEqual(result.status, SteamGameImportStatus.UPDATED)
        game = Game.objects.get(pk=self.original_pk)
        self.assertEqual(game.content_type, "unknown")

    def test_listing_status_preserved_on_update(self):
        self.game.listing_status = ListingStatus.PUBLISHED
        self.game.save()
        self.service.persist(_candidate("620", "Portal 2 — Reloaded"))

        game = Game.objects.get(pk=self.original_pk)
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)

    def test_manual_metadata_preserved_on_update(self):
        self.game.manual_description = "Editorial description."
        self.game.manual_image_url = "https://cdn.example.com/img.png"
        self.game.manual_website_url = "https://example.com"
        self.game.save()
        self.service.persist(_candidate("620", "Portal 2 — Reloaded"))

        game = Game.objects.get(pk=self.original_pk)
        self.assertEqual(game.manual_description, "Editorial description.")
        self.assertEqual(game.manual_image_url, "https://cdn.example.com/img.png")
        self.assertEqual(game.manual_website_url, "https://example.com")

    def test_classification_preserved_on_update(self):
        editor = User.objects.create_user(username="editor")
        parent = set_editorial_classification(
            game=self.game,
            updated_by=editor,
            challenge=ScoreDistribution(50, 20, 30),
            reward=ScoreDistribution(10, 30, 60),
            notes="Original notes.",
        )
        original_notes = parent.notes
        original_challenge = (50, 20, 30)
        original_reward = (10, 30, 60)

        self.service.persist(_candidate("620", "Portal 2 — Reloaded"))

        game = Game.objects.get(pk=self.original_pk)
        classification = EditorialClassification.objects.get(game=game)
        challenge = classification.challenge_profile
        reward = classification.reward_profile
        self.assertEqual(classification.notes, original_notes)
        self.assertEqual(
            classification.updated_by_id,  # pyright: ignore[reportAttributeAccessIssue] — django-stubs FK _id limitation
            editor.pk,
        )
        self.assertEqual(
            (challenge.micro_score, challenge.mystiko_score, challenge.macro_score),
            original_challenge,
        )
        self.assertEqual(
            (reward.micro_score, reward.mystiko_score, reward.macro_score),
            original_reward,
        )

    def test_external_id_never_changes(self):
        self.service.persist(_candidate("620", "Portal 2 — Reloaded"))
        game = Game.objects.get(pk=self.original_pk)
        self.assertEqual(game.external_id, "620")


# ---------------------------------------------------------------------------
# Manual collision behavior
# ---------------------------------------------------------------------------


class ManualCollisionTests(TestCase):
    def setUp(self):
        self.service = SteamGamePersistenceService()

    def test_manual_game_with_same_name_stays_manual(self):
        manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Chess",
            slug="chess",
        )
        result = self.service.persist(_candidate("730", "Chess"))

        manual.refresh_from_db()
        self.assertEqual(manual.source_type, SourceType.MANUAL)
        self.assertIsNone(manual.external_id)
        self.assertEqual(manual.slug, "chess")

        steam = Game.objects.get(pk=result.game_id)
        self.assertEqual(steam.source_type, SourceType.STEAM)
        self.assertEqual(steam.slug, "chess-steam-730")
        self.assertNotEqual(steam.pk, manual.pk)

    def test_manual_game_with_same_preferred_slug_is_not_modified(self):
        manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Something Else",
            slug="portal-2",
        )
        result = self.service.persist(_candidate("620", "Portal 2"))

        manual.refresh_from_db()
        self.assertEqual(manual.slug, "portal-2")
        self.assertEqual(manual.name, "Something Else")

        steam = Game.objects.get(pk=result.game_id)
        self.assertEqual(steam.slug, "portal-2-steam-620")

    def test_never_converts_manual_to_steam(self):
        manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Portal 2",
            slug="portal-2",
        )
        self.service.persist(_candidate("620", "Portal 2"))

        manual.refresh_from_db()
        self.assertEqual(manual.source_type, SourceType.MANUAL)
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="620"
        )
        self.assertEqual(steam_rows.count(), 1)


# ---------------------------------------------------------------------------
# Listing behavior
# ---------------------------------------------------------------------------


class ListingBehaviorTests(TestCase):
    def setUp(self):
        self.service = SteamGamePersistenceService()

    def test_game_draft_not_publicly_listable(self):
        self.service.persist(_candidate("620", "Portal 2"))
        self.assertEqual(Game.objects.publicly_listable().count(), 0)

    def test_published_game_appears_in_listing(self):
        result = self.service.persist(_candidate("620", "Portal 2"))
        game = Game.objects.get(pk=result.game_id)
        game.listing_status = ListingStatus.PUBLISHED
        game.save()
        self.assertIn(game, Game.objects.publicly_listable())

    def test_unknown_stays_excluded_even_published(self):
        result = self.service.persist(
            _candidate("9999", "Mystery", content_type="unknown")
        )
        game = Game.objects.get(pk=result.game_id)
        game.listing_status = ListingStatus.PUBLISHED
        game.save()
        self.assertEqual(Game.objects.publicly_listable().count(), 0)


# ---------------------------------------------------------------------------
# Validation and atomicity
# ---------------------------------------------------------------------------


class ValidationAndAtomicityTests(TestCase):
    def setUp(self):
        self.service = SteamGamePersistenceService()

    def test_invalid_content_type_rejected_without_row(self):
        with self.assertRaises(ValidationError):
            self.service.persist(_candidate("620", "Portal 2", content_type="other"))
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="620"
        )
        self.assertEqual(steam_rows.count(), 0)

    def test_invalid_app_id_rejected_without_row(self):
        with self.assertRaises(ValueError):
            self.service.persist(_candidate("abc", "Portal 2"))
        self.assertEqual(Game.objects.count(), 0)

    def test_failed_update_preserves_existing_state(self):
        created = self.service.persist(_candidate("620", "Portal 2"))
        original = Game.objects.get(pk=created.game_id)

        with self.assertRaises(ValidationError):
            self.service.persist(_candidate("620", "Portal 2", content_type="nope"))

        game = Game.objects.get(pk=created.game_id)
        self.assertEqual(game.name, original.name)
        self.assertEqual(game.content_type, original.content_type)
        self.assertEqual(game.updated_at, original.updated_at)

    def test_integrity_error_without_existing_row_propagates(self):
        with mock.patch.object(Game, "save", side_effect=IntegrityError("boom")):
            with self.assertRaises(IntegrityError):
                self.service.persist(_candidate("888", "Ghost"))
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="888"
        )
        self.assertEqual(steam_rows.count(), 0)

    def test_identity_race_recovers_existing_row(self):
        """A concurrent winner's row is adopted instead of duplicating."""
        raced = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="777",
            name="Raced",
            slug="raced",
        )
        service = SteamGamePersistenceService()

        with mock.patch.object(service, "_find_existing", side_effect=[None, raced]):
            with mock.patch.object(
                Game, "save", side_effect=IntegrityError("unique race")
            ):
                result = service.persist(_candidate("777", "Raced"))

        self.assertEqual(result.status, SteamGameImportStatus.UNCHANGED)
        self.assertEqual(result.game_id, raced.pk)
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="777"
        )
        self.assertEqual(steam_rows.count(), 1)

    def test_identity_race_with_changed_name_updates_winner(self):
        raced = Game.objects.create(
            source_type=SourceType.STEAM,
            external_id="777",
            name="Raced",
            slug="raced",
        )
        service = SteamGamePersistenceService()
        real_save = Game.save
        calls = {"count": 0}

        def racing_save(self, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise IntegrityError("unique race")
            return real_save(self, *args, **kwargs)

        with mock.patch.object(service, "_find_existing", side_effect=[None, raced]):
            with mock.patch.object(Game, "save", new=racing_save):
                result = service.persist(_candidate("777", "Raced — Final"))

        self.assertEqual(result.status, SteamGameImportStatus.UPDATED)
        raced.refresh_from_db()
        self.assertEqual(raced.name, "Raced — Final")


# ---------------------------------------------------------------------------
# Slug-race recovery (distinct App IDs, same name)
# ---------------------------------------------------------------------------


class SlugRaceTests(TransactionTestCase):
    """A different Steam App ID stealing the preferred slug is recoverable.

    Simulates the race window deterministically: the first allocation
    returns the (now stale) preferred slug; the real INSERT fails on the
    real unique slug constraint; recovery recomputes a deterministic slug
    and retries once.
    """

    def test_slug_stolen_between_allocation_and_insert(self):
        # An unrelated Game already owns the preferred slug.
        manual = Game.objects.create(
            source_type=SourceType.MANUAL,
            name="Same Name",
            slug="same-name",
        )

        import games.services.imports.steam as steam_module

        real_allocate = steam_module.build_steam_game_slug
        calls = {"count": 0}

        def stale_allocation(name, app_id, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                # Simulate the race window: allocation saw the slug free.
                return "same-name"
            return real_allocate(name, app_id, **kwargs)

        service = SteamGamePersistenceService()
        with mock.patch.object(
            steam_module, "build_steam_game_slug", side_effect=stale_allocation
        ):
            result = service.persist(_candidate("777002", "Same Name"))

        self.assertEqual(result.status, SteamGameImportStatus.CREATED)

        steam = Game.objects.get(pk=result.game_id)
        self.assertEqual(steam.external_id, "777002")
        # Deterministic policy: preferred slug taken → suffixed candidate.
        self.assertEqual(steam.slug, "same-name-steam-777002")

        # The unrelated Game is untouched.
        manual.refresh_from_db()
        self.assertEqual(manual.slug, "same-name")
        self.assertEqual(manual.source_type, SourceType.MANUAL)

    def test_unrelated_integrity_error_still_propagates(self):
        """No occupied slug and no identity row → the error is unrelated."""
        service = SteamGamePersistenceService()
        with mock.patch.object(Game, "save", side_effect=IntegrityError("boom")):
            with self.assertRaises(IntegrityError):
                service.persist(_candidate("777003", "Unique Name"))
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="777003"
        )
        self.assertEqual(steam_rows.count(), 0)


# ---------------------------------------------------------------------------
# Steam image persistence — SBGC-55
# ---------------------------------------------------------------------------


class SteamImageTests(TestCase):
    """steam_image_url ownership, update, and preservation semantics."""

    def setUp(self):
        self.service = SteamGamePersistenceService()

    # -- new imports ---------------------------------------------------------

    def test_new_import_stores_image_url(self):
        image = "https://cdn.example.com/steam/apps/620/header.jpg"
        result = self.service.persist(
            _candidate("620", "Portal 2", header_image_url=image)
        )

        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.steam_image_url, image)

    def test_new_import_without_image_has_empty_url(self):
        result = self.service.persist(_candidate("620", "Portal 2"))

        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.steam_image_url, "")

    def test_new_import_with_malformed_url_raises_without_row(self):
        with self.assertRaises(SteamMalformedPayloadError):
            self.service.persist(
                _candidate(
                    "620", "Portal 2", header_image_url="http://cdn.example.com/x.jpg"
                )
            )
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="620"
        )
        self.assertEqual(steam_rows.count(), 0)

    def test_new_import_never_populates_manual_image(self):
        image = "https://cdn.example.com/steam/apps/620/header.jpg"
        result = self.service.persist(
            _candidate("620", "Portal 2", header_image_url=image)
        )

        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.manual_image_url, "")

    def test_non_string_image_url_raises_without_row(self):
        with self.assertRaises(SteamMalformedPayloadError):
            self.service.persist(
                _candidate(
                    "620",
                    "Portal 2",
                    header_image_url=123,  # type: ignore[arg-type]
                )
            )
        steam_rows = Game.objects.filter(
            source_type=SourceType.STEAM, external_id="620"
        )
        self.assertEqual(steam_rows.count(), 0)

    # -- re-imports ----------------------------------------------------------

    def test_reimport_changed_image_updates(self):
        first = self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/a.jpg"
            )
        )
        image_b = "https://cdn.example.com/b.jpg"
        second = self.service.persist(
            _candidate("620", "Portal 2", header_image_url=image_b)
        )

        self.assertEqual(second.status, SteamGameImportStatus.UPDATED)
        game = Game.objects.get(pk=first.game_id)
        self.assertEqual(game.steam_image_url, image_b)

    def test_reimport_same_image_unchanged(self):
        image = "https://cdn.example.com/a.jpg"
        self.service.persist(_candidate("620", "Portal 2", header_image_url=image))
        result = self.service.persist(
            _candidate("620", "Portal 2", header_image_url=image)
        )

        self.assertEqual(result.status, SteamGameImportStatus.UNCHANGED)

    def test_reimport_missing_image_preserves_existing(self):
        image = "https://cdn.example.com/a.jpg"
        self.service.persist(_candidate("620", "Portal 2", header_image_url=image))

        # Upstream absence (None) preserves — this is the missing-image
        # contract, distinct from malformed metadata which raises.
        result = self.service.persist(_candidate("620", "Portal 2"))

        self.assertEqual(result.status, SteamGameImportStatus.UNCHANGED)
        game = Game.objects.get(source_type=SourceType.STEAM, external_id="620")
        self.assertEqual(game.steam_image_url, image)

    def test_reimport_malformed_image_raises_and_preserves_existing(self):
        image = "https://cdn.example.com/a.jpg"
        created = self.service.persist(
            _candidate("620", "Portal 2", header_image_url=image)
        )

        # Malformed nonblank candidate metadata is an error — it is never
        # reclassified as absence, so nothing is written.
        with self.assertRaises(SteamMalformedPayloadError):
            self.service.persist(
                _candidate(
                    "620", "Portal 2", header_image_url="http://cdn.example.com/x.jpg"
                )
            )

        game = Game.objects.get(pk=created.game_id)
        self.assertEqual(game.steam_image_url, image)

    def test_image_update_preserves_manual_metadata(self):
        created = self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/a.jpg"
            )
        )
        game = Game.objects.get(pk=created.game_id)
        game.manual_description = "Editorial description."
        game.manual_image_url = "https://cdn.example.com/manual.png"
        game.manual_website_url = "https://example.com"
        game.save()

        self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/b.jpg"
            )
        )

        game.refresh_from_db()
        self.assertEqual(game.manual_description, "Editorial description.")
        self.assertEqual(game.manual_image_url, "https://cdn.example.com/manual.png")
        self.assertEqual(game.manual_website_url, "https://example.com")

    def test_image_update_preserves_listing_status(self):
        created = self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/a.jpg"
            )
        )
        game = Game.objects.get(pk=created.game_id)
        game.listing_status = ListingStatus.PUBLISHED
        game.save()

        self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/b.jpg"
            )
        )

        game.refresh_from_db()
        self.assertEqual(game.listing_status, ListingStatus.PUBLISHED)

    def test_image_update_preserves_classification(self):
        created = self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/a.jpg"
            )
        )
        game = Game.objects.get(pk=created.game_id)
        editor = User.objects.create_user(username="image-editor")
        set_editorial_classification(
            game=game,
            updated_by=editor,
            challenge=ScoreDistribution(50, 20, 30),
            reward=ScoreDistribution(10, 30, 60),
            notes="Keep me.",
        )

        self.service.persist(
            _candidate(
                "620", "Portal 2", header_image_url="https://cdn.example.com/b.jpg"
            )
        )

        game = Game.objects.get(pk=created.game_id)
        classification = EditorialClassification.objects.get(game=game)
        self.assertEqual(classification.notes, "Keep me.")
        self.assertEqual(classification.challenge_profile.micro_score, 50)
        self.assertEqual(classification.reward_profile.macro_score, 60)

    # -- no network ----------------------------------------------------------

    def test_image_persistence_makes_no_http_request(self):
        """URL-only persistence must not fetch, HEAD, or resolve the URL."""
        image = "https://cdn.example.com/steam/apps/620/header.jpg"
        with mock.patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("Steam transport must not be used"),
        ):
            result = self.service.persist(
                _candidate("620", "Portal 2", header_image_url=image)
            )
        self.assertEqual(result.status, SteamGameImportStatus.CREATED)
        game = Game.objects.get(pk=result.game_id)
        self.assertEqual(game.steam_image_url, image)


# ---------------------------------------------------------------------------
# No network
# ---------------------------------------------------------------------------


class NoNetworkTests(TestCase):
    def test_persist_never_constructs_steam_client(self):
        """Persistence must succeed even if Steam transport is impossible."""
        with mock.patch(
            "games.services.steam.client.SteamClient.__init__",
            side_effect=RuntimeError("Steam transport must not be used"),
        ):
            service = SteamGamePersistenceService()
            result = service.persist(_candidate("620", "Portal 2"))
        self.assertEqual(result.status, SteamGameImportStatus.CREATED)
