"""
Deterministic Steam import slugging — SBGC-54.

Pure-function tests for ``build_steam_game_slug``.  No database —
occupancy is injected as a predicate.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from games.services.imports.steam import build_steam_game_slug


def _occupied(*slugs: str):
    taken = set(slugs)

    def is_occupied(candidate: str) -> bool:
        return candidate in taken

    return is_occupied


class PreferredSlugTests(SimpleTestCase):
    def test_slugifies_name(self):
        self.assertEqual(
            build_steam_game_slug("Portal 2", "620"),
            "portal-2",
        )

    def test_strips_punctuation(self):
        self.assertEqual(
            build_steam_game_slug("Hades: Supergiant!", "1145360"),
            "hades-supergiant",
        )

    def test_returns_same_slug_deterministically(self):
        first = build_steam_game_slug("Team Fortress 2", "440")
        second = build_steam_game_slug("Team Fortress 2", "440")
        self.assertEqual(first, second)


class FallbackSlugTests(SimpleTestCase):
    def test_blank_slugified_name_uses_steam_app_id(self):
        self.assertEqual(
            build_steam_game_slug("!!!", "1234"),
            "steam-1234",
        )

    def test_unicode_only_name_uses_steam_app_id(self):
        self.assertEqual(
            build_steam_game_slug("游戏", "5678"),
            "steam-5678",
        )

    def test_whitespace_only_name_uses_steam_app_id(self):
        self.assertEqual(
            build_steam_game_slug("   ", "999"),
            "steam-999",
        )


class OccupiedSlugTests(SimpleTestCase):
    def test_occupied_preferred_uses_app_id_suffix(self):
        result = build_steam_game_slug("Chess", "730", is_occupied=_occupied("chess"))
        self.assertEqual(result, "chess-steam-730")

    def test_occupied_preferred_and_suffixed_uses_fallback(self):
        result = build_steam_game_slug(
            "Chess",
            "730",
            is_occupied=_occupied("chess", "chess-steam-730"),
        )
        self.assertEqual(result, "steam-730")

    def test_blank_name_with_occupied_fallback_raises(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug(
                "!!!",
                "730",
                is_occupied=_occupied("steam-730"),
            )

    def test_all_candidates_occupied_raises(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug(
                "Chess",
                "730",
                is_occupied=_occupied("chess", "chess-steam-730", "steam-730"),
            )


class LengthTests(SimpleTestCase):
    def test_long_name_truncated_to_max_length(self):
        result = build_steam_game_slug("A" * 500, "730")
        self.assertLessEqual(len(result), 255)
        self.assertTrue(result.startswith("a" * 200))

    def test_truncation_preserves_app_id_suffix(self):
        occupied_long = build_steam_game_slug("B" * 500, "42")
        self.assertLessEqual(len(occupied_long), 255)
        # Preferred is free — truncated base without suffix.
        self.assertEqual(len(occupied_long), 255)
        self.assertFalse(occupied_long.endswith("-steam-42"))

        suffixed = build_steam_game_slug(
            "C" * 500,
            "42",
            is_occupied=_occupied("c" * 255),
        )
        self.assertLessEqual(len(suffixed), 255)
        self.assertTrue(suffixed.endswith("-steam-42"))

    def test_no_trailing_hyphen_after_truncation(self):
        # "ab-ab-ab..." truncated at 255 lands on a hyphen — rstrip removes it.
        name = " ".join(["ab"] * 300)
        result = build_steam_game_slug(name, "7")
        self.assertLessEqual(len(result), 255)
        self.assertFalse(result.endswith("-"))


class ValidationTests(SimpleTestCase):
    def test_non_string_name_rejected(self):
        with self.assertRaises(TypeError):
            build_steam_game_slug(123, "730")  # type: ignore[arg-type]

    def test_non_string_app_id_rejected(self):
        with self.assertRaises(TypeError):
            build_steam_game_slug("Chess", 730)  # type: ignore[arg-type]

    def test_blank_app_id_rejected(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug("Chess", "")

    def test_whitespace_app_id_rejected(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug("Chess", "  ")

    def test_nondigit_app_id_rejected(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug("Chess", "abc")

    def test_zero_app_id_rejected(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug("Chess", "0")

    def test_invalid_max_length_rejected(self):
        with self.assertRaises(ValueError):
            build_steam_game_slug("Chess", "730", max_length=0)

    def test_boolean_max_length_rejected(self):
        with self.assertRaises(TypeError):
            build_steam_game_slug("Chess", "730", max_length=True)  # type: ignore[arg-type]

    def test_non_callable_occupancy_rejected(self):
        with self.assertRaises(TypeError):
            build_steam_game_slug("Chess", "730", is_occupied="nope")  # type: ignore[arg-type]
