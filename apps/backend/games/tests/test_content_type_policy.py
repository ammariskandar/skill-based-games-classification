"""
Content-type policy contract tests — SBGC-94.

Locks the canonical content-type policy at the contract level: the exact
6-value taxonomy, the Steam product-type mapping truth table, and the public
listing gate.  Complements the behavioral coverage in ``test_listing_rules``
(SBGC-48) and ``services/steam/test_mapping`` (SBGC-53).  No production code
is modified — this suite only pins the existing contract.
"""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from games.models import ContentType, Game, ListingStatus, SourceType
from games.services.steam.mapping import map_steam_product_type
from games.types import CONTENT_TYPE_CHOICES

# ---------------------------------------------------------------------------
# Canonical taxonomy
# ---------------------------------------------------------------------------


class TaxonomyContractTests(SimpleTestCase):
    """The 6-value taxonomy is the single source of truth."""

    def test_exactly_six_canonical_values(self):
        self.assertEqual(
            set(ContentType),
            {
                ContentType.GAME,
                ContentType.DLC,
                ContentType.DEMO,
                ContentType.SOFTWARE,
                ContentType.SOUNDTRACK,
                ContentType.UNKNOWN,
            },
        )

    def test_choices_cover_every_enum_value_with_clean_labels(self):
        self.assertEqual(
            {value for value, _ in CONTENT_TYPE_CHOICES},
            {member.value for member in ContentType},
        )
        for _, label in CONTENT_TYPE_CHOICES:
            with self.subTest(label=label):
                self.assertTrue(label.strip())
                self.assertEqual(label, label.strip())


# ---------------------------------------------------------------------------
# Steam type mapping
# ---------------------------------------------------------------------------


class SteamMappingContractTests(SimpleTestCase):
    """Deterministic raw-Steam-type → canonical-type mapping (SBGC-53)."""

    def test_mapped_product_types(self):
        cases = {
            "game": ContentType.GAME,
            "dlc": ContentType.DLC,
            "demo": ContentType.DEMO,
            "software": ContentType.SOFTWARE,
            "music": ContentType.SOUNDTRACK,
            "soundtrack": ContentType.SOUNDTRACK,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(map_steam_product_type(raw), expected)

    def test_unrecognized_types_fall_back_to_unknown(self):
        # Steam emits many more type strings than the taxonomy models; every
        # one of them (including "application") must bucket to UNKNOWN, never
        # to a game-eligible type.
        for raw in (
            "application",
            "tool",
            "hardware",
            "video",
            "series",
            "episode",
            "mod",
            "advertising",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(map_steam_product_type(raw), ContentType.UNKNOWN)

    def test_malformed_input_raises(self):
        for raw in ("", "   ", None, 123, True):
            with self.subTest(raw=repr(raw)):
                with self.assertRaises(ValueError):
                    map_steam_product_type(raw)


# ---------------------------------------------------------------------------
# Public eligibility
# ---------------------------------------------------------------------------


class PublicEligibilityContractTests(TestCase):
    """Only Published GAME records pass the public listing gate."""

    def _make(self, content_type: ContentType, status: ListingStatus) -> Game:
        return Game.objects.create(
            name=f"Product {content_type.value}",
            slug=f"product-{content_type.value}",
            source_type=SourceType.MANUAL,
            content_type=content_type,
            listing_status=status,
        )

    def test_only_published_game_is_listable(self):
        published = {
            content_type: self._make(content_type, ListingStatus.PUBLISHED)
            for content_type in ContentType
        }

        listable = list(Game.objects.publicly_listable())
        self.assertEqual(listable, [published[ContentType.GAME]])

    def test_game_requires_published_status(self):
        game = self._make(ContentType.GAME, ListingStatus.DRAFT)
        self.assertNotIn(game, Game.objects.publicly_listable())

        game.listing_status = ListingStatus.ARCHIVED
        game.save()
        self.assertNotIn(game, Game.objects.publicly_listable())
