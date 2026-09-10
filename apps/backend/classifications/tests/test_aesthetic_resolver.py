"""
Aesthetic classification resolver tests — SBGC-172 (Epic SBGC-171).

Covers the Q1/Q2 option registry, the combinatoric resolution matrix (true,
hybrid, collaborative collapse, none-collapse, special flow), the question-set
dispatch contract, the model field, and the Ninja resolve-aesthetic endpoint.
"""

from __future__ import annotations

import json
from itertools import product

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from games.models import Aesthetic, Game, SourceType

from classifications.questionnaire.aesthetic_resolver import (
    PART1_SET_MAP,
    PART2_SET_MAP,
    resolve_aesthetic,
    resolve_from_options,
)
from classifications.questionnaire.domain import (
    NONE_OPTION,
    OPTION_BY_ID,
    PRIMARY_OPTIONS,
    AestheticCategory,
    InvalidOptionSelectionError,
    QuestionSetId,
    UnknownOptionError,
    UnresolvableAestheticError,
    available_secondary_options,
    map_option_to_category,
)

RESOLVE_URL = "/api/v1/questionnaire/resolve-aesthetic"

CANONICAL = (
    AestheticCategory.SENSORY,
    AestheticCategory.FANTASY,
    AestheticCategory.NARRATIVE,
    AestheticCategory.CHALLENGE,
)


def _published_game(name: str = "Aesthetic Test Game") -> Game:
    return Game.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        source_type=SourceType.MANUAL,
        content_type="game",
        listing_status="published",
    )


class OptionRegistryTests(SimpleTestCase):
    def test_primary_options_are_the_seventeen_q1_options(self):
        self.assertEqual(len(PRIMARY_OPTIONS), 17)
        self.assertNotIn(NONE_OPTION.option_id, {o.option_id for o in PRIMARY_OPTIONS})
        self.assertEqual(len(OPTION_BY_ID), 18)

    def test_option_taxonomy_matches_the_canonical_table(self):
        expected = {
            "OPT_S1": AestheticCategory.SENSORY,
            "OPT_S2": AestheticCategory.SENSORY,
            "OPT_S3": AestheticCategory.SENSORY,
            "OPT_S4": AestheticCategory.SENSORY,
            "OPT_S5": AestheticCategory.SENSORY,
            "OPT_S6": AestheticCategory.SENSORY,
            "OPT_F1": AestheticCategory.FANTASY,
            "OPT_F2": AestheticCategory.FANTASY,
            "OPT_F3": AestheticCategory.FANTASY,
            "OPT_F4": AestheticCategory.FANTASY,
            "OPT_N1": AestheticCategory.NARRATIVE,
            "OPT_N2": AestheticCategory.NARRATIVE,
            "OPT_C1": AestheticCategory.CHALLENGE,
            "OPT_C2": AestheticCategory.CHALLENGE,
            "OPT_C3": AestheticCategory.CHALLENGE,
            "OPT_C4": AestheticCategory.CHALLENGE,
            "OPT_COL": AestheticCategory.COLLABORATIVE,
            "OPT_NONE": AestheticCategory.NONE,
        }
        self.assertEqual(
            {key: map_option_to_category(key) for key in expected},
            expected,
        )

    def test_q2_options_exclude_the_q1_selection_and_always_include_none(self):
        options = available_secondary_options("OPT_S1")
        option_ids = [option.option_id for option in options]
        self.assertNotIn("OPT_S1", option_ids)
        self.assertEqual(option_ids[-1], NONE_OPTION.option_id)
        self.assertEqual(len(options), 17)

        collab_options = available_secondary_options("OPT_COL")
        collab_ids = {option.option_id for option in collab_options}
        self.assertNotIn("OPT_COL", collab_ids)
        self.assertEqual(len(collab_options), 17)

    def test_unknown_or_none_q1_selection_is_rejected(self):
        with self.assertRaises(UnknownOptionError):
            map_option_to_category("OPT_NOT_REAL")
        with self.assertRaises(InvalidOptionSelectionError):
            available_secondary_options(NONE_OPTION.option_id)


class TrueAestheticTests(SimpleTestCase):
    def test_identical_categories_resolve_to_true_aesthetics(self):
        for category in CANONICAL:
            with self.subTest(category=category):
                result = resolve_aesthetic(category, category)
                self.assertTrue(result.is_true_aesthetic)
                self.assertEqual(result.dominant_aesthetic, category)
                self.assertIsNone(result.secondary_aesthetic)
                self.assertEqual(result.part1_challenge_set, PART1_SET_MAP[category])
                self.assertFalse(result.part2_reward_config.is_split)
                self.assertEqual(
                    result.part2_reward_config.q9_to_q11_set, PART2_SET_MAP[category]
                )
                self.assertEqual(
                    result.part2_reward_config.q12_to_q14_set, PART2_SET_MAP[category]
                )

    def test_collaborative_collapse_q1(self):
        result = resolve_aesthetic(
            AestheticCategory.COLLABORATIVE, AestheticCategory.CHALLENGE
        )
        self.assertTrue(result.is_true_aesthetic)
        self.assertEqual(result.dominant_aesthetic, AestheticCategory.CHALLENGE)
        self.assertIsNone(result.secondary_aesthetic)
        self.assertEqual(result.part1_challenge_set, QuestionSetId.SET_1D)
        self.assertEqual(result.part2_reward_config.q9_to_q11_set, QuestionSetId.SET_2D)
        self.assertEqual(
            result.part2_reward_config.q12_to_q14_set, QuestionSetId.SET_2D
        )

    def test_collaborative_collapse_q2(self):
        result = resolve_aesthetic(
            AestheticCategory.NARRATIVE, AestheticCategory.COLLABORATIVE
        )
        self.assertTrue(result.is_true_aesthetic)
        self.assertEqual(result.dominant_aesthetic, AestheticCategory.NARRATIVE)
        self.assertEqual(result.part1_challenge_set, QuestionSetId.SET_1C)

    def test_none_of_the_above_collapse(self):
        result = resolve_aesthetic(AestheticCategory.FANTASY, AestheticCategory.NONE)
        self.assertTrue(result.is_true_aesthetic)
        self.assertEqual(result.dominant_aesthetic, AestheticCategory.FANTASY)
        self.assertIsNone(result.secondary_aesthetic)
        self.assertEqual(result.part1_challenge_set, QuestionSetId.SET_1B)

    def test_special_flow_trigger(self):
        result = resolve_aesthetic(
            AestheticCategory.COLLABORATIVE, AestheticCategory.NONE
        )
        self.assertFalse(result.is_true_aesthetic)
        self.assertEqual(result.dominant_aesthetic, AestheticCategory.SPECIAL_FLOW)
        self.assertIsNone(result.secondary_aesthetic)
        self.assertEqual(result.part1_challenge_set, QuestionSetId.SPECIAL)
        self.assertFalse(result.part2_reward_config.is_split)
        self.assertEqual(
            result.part2_reward_config.q9_to_q11_set, QuestionSetId.SPECIAL
        )
        self.assertEqual(
            result.part2_reward_config.q12_to_q14_set, QuestionSetId.SPECIAL
        )


class HybridAestheticTests(SimpleTestCase):
    def test_sensory_and_fantasy_split(self):
        result = resolve_aesthetic(AestheticCategory.SENSORY, AestheticCategory.FANTASY)
        self.assertFalse(result.is_true_aesthetic)
        self.assertEqual(result.dominant_aesthetic, AestheticCategory.SENSORY)
        self.assertEqual(result.secondary_aesthetic, AestheticCategory.FANTASY)
        self.assertEqual(result.part1_challenge_set, QuestionSetId.SET_1A)
        self.assertTrue(result.part2_reward_config.is_split)
        # Q9-Q11 come from the secondary set, Q12-Q14 from the dominant set.
        self.assertEqual(result.part2_reward_config.q9_to_q11_set, QuestionSetId.SET_2B)
        self.assertEqual(
            result.part2_reward_config.q12_to_q14_set, QuestionSetId.SET_2A
        )

    def test_all_ordered_hybrid_pairs_are_split_and_dominant_first(self):
        for cat1, cat2 in product(CANONICAL, repeat=2):
            if cat1 == cat2:
                continue
            with self.subTest(cat1=cat1, cat2=cat2):
                result = resolve_aesthetic(cat1, cat2)
                self.assertFalse(result.is_true_aesthetic)
                self.assertEqual(result.dominant_aesthetic, cat1)
                self.assertEqual(result.secondary_aesthetic, cat2)
                self.assertEqual(result.part1_challenge_set, PART1_SET_MAP[cat1])
                self.assertTrue(result.part2_reward_config.is_split)
                self.assertEqual(
                    result.part2_reward_config.q9_to_q11_set, PART2_SET_MAP[cat2]
                )
                self.assertEqual(
                    result.part2_reward_config.q12_to_q14_set, PART2_SET_MAP[cat1]
                )

    def test_unresolvable_pairs_are_rejected(self):
        with self.assertRaises(UnresolvableAestheticError):
            resolve_aesthetic(
                AestheticCategory.COLLABORATIVE, AestheticCategory.COLLABORATIVE
            )
        with self.assertRaises(UnresolvableAestheticError):
            resolve_aesthetic(AestheticCategory.NONE, AestheticCategory.SENSORY)


class ResolveFromOptionsTests(SimpleTestCase):
    def test_resolves_hybrid_from_option_ids(self):
        result = resolve_from_options("OPT_S1", "OPT_F1")
        self.assertEqual(result.dominant_aesthetic, AestheticCategory.SENSORY)
        self.assertEqual(result.secondary_aesthetic, AestheticCategory.FANTASY)

    def test_rejects_none_in_q1(self):
        with self.assertRaises(InvalidOptionSelectionError):
            resolve_from_options("OPT_NONE", "OPT_S1")

    def test_rejects_replaying_the_q1_option_in_q2(self):
        with self.assertRaises(InvalidOptionSelectionError):
            resolve_from_options("OPT_S1", "OPT_S1")

    def test_rejects_unknown_options(self):
        with self.assertRaises(UnknownOptionError):
            resolve_from_options("OPT_BOGUS", "OPT_S1")
        with self.assertRaises(UnknownOptionError):
            resolve_from_options("OPT_S1", "OPT_BOGUS")

    def test_every_q2_option_offered_for_a_q1_selection_resolves(self):
        for option in available_secondary_options("OPT_COL"):
            with self.subTest(q2=option.option_id):
                result = resolve_from_options("OPT_COL", option.option_id)
                self.assertIn(
                    result.dominant_aesthetic,
                    (*CANONICAL, AestheticCategory.SPECIAL_FLOW),
                )


class GameAestheticFieldTests(TestCase):
    def test_aesthetic_defaults_to_unresolved(self):
        game = _published_game()
        self.assertIsNone(game.aesthetic)

    def test_aesthetic_accepts_canonical_values(self):
        game = _published_game()
        game.aesthetic = Aesthetic.SENSORY
        game.save()
        game.refresh_from_db()
        self.assertEqual(game.aesthetic, "SENSORY")

    def test_aesthetic_rejects_non_canonical_values(self):
        game = _published_game()
        game.aesthetic = "NOT_AN_AESTHETIC"
        with self.assertRaises(ValidationError):
            game.full_clean()


class ResolveAestheticEndpointTests(TestCase):
    def _post(self, body: dict):
        return self.client.post(
            RESOLVE_URL,
            data=json.dumps(body),
            content_type="application/json",
        )

    def test_game_not_found_returns_404(self):
        response = self._post(
            {
                "game_slug": "does-not-exist",
                "q1_option_id": "OPT_S1",
                "q2_option_id": "OPT_F1",
            }
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_non_public_game_returns_404(self):
        game = _published_game()
        game.listing_status = "draft"
        game.save()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_S1",
                "q2_option_id": "OPT_F1",
            }
        )
        self.assertEqual(response.status_code, 404)

    def test_hybrid_resolution_payload(self):
        game = _published_game()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_S1",
                "q2_option_id": "OPT_F1",
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["game_slug"], game.slug)
        self.assertEqual(body["game_name"], game.name)
        self.assertEqual(body["dominant_aesthetic"], "SENSORY")
        self.assertEqual(body["secondary_aesthetic"], "FANTASY")
        self.assertFalse(body["is_true_aesthetic"])
        self.assertEqual(body["part1_challenge_set"], "1A")
        self.assertEqual(
            body["part2_reward_config"],
            {"is_split": True, "q9_to_q11_set": "2B", "q12_to_q14_set": "2A"},
        )

    def test_true_aesthetic_resolution_payload(self):
        game = _published_game()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_C1",
                "q2_option_id": "OPT_NONE",
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["dominant_aesthetic"], "CHALLENGE")
        self.assertIsNone(body["secondary_aesthetic"])
        self.assertTrue(body["is_true_aesthetic"])
        self.assertEqual(body["part1_challenge_set"], "1D")

    def test_invalid_option_returns_422(self):
        game = _published_game()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_NONE",
                "q2_option_id": "OPT_S1",
            }
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
