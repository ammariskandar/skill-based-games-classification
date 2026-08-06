"""
Steam product-type mapping tests — SBGC-53.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from games.services.steam.mapping import map_steam_product_type


class ProductTypeMappingTests(SimpleTestCase):
    def test_game(self):
        self.assertEqual(map_steam_product_type("game"), "game")

    def test_dlc(self):
        self.assertEqual(map_steam_product_type("dlc"), "dlc")

    def test_demo(self):
        self.assertEqual(map_steam_product_type("demo"), "demo")

    def test_software(self):
        self.assertEqual(map_steam_product_type("software"), "software")

    def test_music(self):
        self.assertEqual(map_steam_product_type("music"), "soundtrack")

    def test_soundtrack(self):
        self.assertEqual(map_steam_product_type("soundtrack"), "soundtrack")

    def test_mixed_case(self):
        self.assertEqual(map_steam_product_type("Game"), "game")
        self.assertEqual(map_steam_product_type("DLC"), "dlc")

    def test_whitespace_stripped(self):
        self.assertEqual(map_steam_product_type("  game  "), "game")

    def test_unknown_type(self):
        self.assertEqual(map_steam_product_type("video"), "unknown")
        self.assertEqual(map_steam_product_type("hardware"), "unknown")

    def test_blank_rejected(self):
        with self.assertRaises(ValueError):
            map_steam_product_type("")

    def test_whitespace_only_rejected(self):
        with self.assertRaises(ValueError):
            map_steam_product_type("   ")

    def test_non_string_rejected(self):
        with self.assertRaises(ValueError):
            map_steam_product_type(123)

    def test_bool_rejected(self):
        with self.assertRaises(ValueError):
            map_steam_product_type(True)

    def test_none_rejected(self):
        with self.assertRaises(ValueError):
            map_steam_product_type(None)

    def test_unknown_not_game(self):
        self.assertNotEqual(map_steam_product_type("mod"), "game")
