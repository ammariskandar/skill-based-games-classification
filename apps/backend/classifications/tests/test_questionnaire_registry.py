"""
Versioned questionnaire registry & hybrid assembler tests — SBGC-173.

Covers graph invariants (root cardinality, acyclicity, dangling targets,
target integrity, branch reachability), the 16-aesthetic permutation matrix
for the hybrid assembler, scoring-modifier fidelity anchors, and the
``/api/v1/questionnaire/assemble-tree`` endpoint contract.
"""

from __future__ import annotations

import json
from dataclasses import replace
from itertools import product

from django.test import SimpleTestCase, TestCase
from games.models import Game, SourceType

from classifications.questionnaire.aesthetic_resolver import resolve_aesthetic
from classifications.questionnaire.domain import AestheticCategory
from classifications.questionnaire.registry.v1.assembler import (
    DOMINANT_PART2_ROOTS,
    REGISTRY_MAP,
    SECONDARY_PART2_ROOTS,
    QuestionnaireRegistryError,
    assemble_questionnaire,
)
from classifications.questionnaire.registry.v1.set_a import SET_A
from classifications.questionnaire.registry.v1.set_b import SET_B
from classifications.questionnaire.registry.v1.set_c import SET_C
from classifications.questionnaire.registry.v1.set_d import SET_D
from classifications.questionnaire.registry.v1.types import (
    REGISTRY_VERSION,
    AssembledQuestionnaire,
    QuestionNode,
    QuestionRegistryError,
    QuestionSetDefinition,
    ScoreModifier,
    validate_question_set,
)

ALL_SETS = (SET_A, SET_B, SET_C, SET_D)

PART1_ROOT_IDS = ["Q3", "Q4", "Q5", "Q6", "Q7", "Q8"]
PART2_ROOT_IDS = ["Q9", "Q10", "Q11", "Q12", "Q13", "Q14"]

ASSEMBLE_URL = "/api/v1/questionnaire/assemble-tree"


def _distinct_root_ids(nodes: tuple[QuestionNode, ...]) -> list[str]:
    seen: list[str] = []
    for node in nodes:
        if node.root_id not in seen:
            seen.append(node.root_id)
    return seen


def _payload_root_ids(nodes: list[dict]) -> list[str]:
    seen: list[str] = []
    for node in nodes:
        if node["root_id"] not in seen:
            seen.append(node["root_id"])
    return seen


def _node_by_id(nodes: tuple[QuestionNode, ...], node_id: str) -> QuestionNode:
    for node in nodes:
        if node.id == node_id:
            return node
    raise AssertionError(f"node '{node_id}' not found")


class RegistryStructureTests(SimpleTestCase):
    def test_every_set_has_six_part1_and_six_part2_roots(self):
        for definition in ALL_SETS:
            with self.subTest(set=definition.set_id):
                part1_roots = _distinct_root_ids(definition.part1_questions)
                part2_roots = _distinct_root_ids(definition.part2_questions)
                self.assertEqual(part1_roots, PART1_ROOT_IDS)
                self.assertEqual(part2_roots, PART2_ROOT_IDS)

    def test_target_integrity(self):
        for definition in ALL_SETS:
            with self.subTest(set=definition.set_id):
                for node in definition.part1_questions:
                    self.assertEqual(node.target.value, "CHALLENGE", node.id)
                for node in definition.part2_questions:
                    self.assertEqual(node.target.value, "REWARD", node.id)

    def test_option_ids_are_unique_within_a_set(self):
        for definition in ALL_SETS:
            with self.subTest(set=definition.set_id):
                ids: list[str] = []
                for node in (*definition.part1_questions, *definition.part2_questions):
                    self.assertTrue(node.options, node.id)
                    ids.extend(option.id for option in node.options)
                self.assertEqual(len(ids), len(set(ids)))

    def test_no_dangling_targets_and_no_profile_crossings(self):
        for definition in ALL_SETS:
            with self.subTest(set=definition.set_id):
                for part in (
                    definition.part1_questions,
                    definition.part2_questions,
                ):
                    by_id = {node.id: node for node in part}
                    for node in part:
                        for option in node.options:
                            target = option.next_question_id
                            if target is None:
                                continue
                            self.assertIn(target, by_id)
                            self.assertEqual(by_id[target].target, node.target)

    def test_branch_graphs_are_acyclic(self):
        # validate_question_set performs the cycle check; a validated set means
        # the branch graph terminates.  Walk it explicitly as a second guard.
        for definition in ALL_SETS:
            with self.subTest(set=definition.set_id):
                for part in (
                    definition.part1_questions,
                    definition.part2_questions,
                ):
                    by_id = {node.id: node for node in part}
                    roots = [node.id for node in part if not node.is_branch]
                    seen: set[str] = set()
                    frontier = list(roots)
                    steps = 0
                    limit = len(part) * len(part) + 1
                    while frontier:
                        steps += 1
                        self.assertLess(steps, limit, "traversal did not terminate")
                        current = frontier.pop()
                        if current in seen:
                            continue
                        seen.add(current)
                        for option in by_id[current].options:
                            if option.next_question_id is not None:
                                frontier.append(option.next_question_id)

    def test_branch_nodes_stay_with_their_root(self):
        for definition in ALL_SETS:
            with self.subTest(set=definition.set_id):
                for node in (*definition.part1_questions, *definition.part2_questions):
                    if node.is_branch:
                        self.assertNotEqual(node.id, node.root_id)
                        self.assertTrue(node.id.startswith(node.root_id))

    def test_validation_rejects_a_dangling_branch_target(self):
        q3 = _node_by_id(SET_A.part1_questions, "Q3")
        dangling = replace(
            q3,
            options=(
                replace(q3.options[0], next_question_id="Q99"),
                *q3.options[1:],
            ),
        )
        definition = QuestionSetDefinition(
            version=REGISTRY_VERSION,
            set_id="TEST",
            name="Broken",
            part1_questions=(
                dangling,
                *[node for node in SET_A.part1_questions if node.id != "Q3"],
            ),
            part2_questions=SET_A.part2_questions,
        )
        with self.assertRaises(QuestionRegistryError):
            validate_question_set(definition)


class ScoreModifierFidelityTests(SimpleTestCase):
    """Anchors shared with the TypeScript mirror (dual-stack parity)."""

    def _option(self, definition, node_id: str, option_suffix: str) -> ScoreModifier:
        node = _node_by_id(
            (*definition.part1_questions, *definition.part2_questions), node_id
        )
        for option in node.options:
            if option.id.endswith(option_suffix):
                return option.modifiers
        raise AssertionError(f"option {option_suffix} not found on {node_id}")

    def test_set_a_weights(self):
        self.assertEqual(self._option(SET_A, "Q3", "huge"), ScoreModifier(micro=20))
        self.assertEqual(
            self._option(SET_A, "Q7", "no_opponents"), ScoreModifier(mystiko=-100)
        )
        self.assertEqual(self._option(SET_A, "Q11A", "yes"), ScoreModifier(mystiko=200))
        self.assertEqual(
            self._option(SET_A, "Q14", "cheaters"), ScoreModifier(micro=30, macro=60)
        )

    def test_set_b_weights(self):
        self.assertEqual(
            self._option(SET_B, "Q3", "frame_perfect"), ScoreModifier(micro=85)
        )
        self.assertEqual(
            self._option(SET_B, "Q10", "vistas_score"), ScoreModifier(mystiko=120)
        )

    def test_set_c_weights(self):
        self.assertEqual(
            self._option(SET_C, "Q3", "gunplay_reflexes"), ScoreModifier(micro=75)
        )
        self.assertEqual(
            self._option(SET_C, "Q6B", "unoptimized_party"),
            ScoreModifier(macro=75, mystiko=15),
        )

    def test_set_d_weights(self):
        self.assertEqual(
            self._option(SET_D, "Q4B", "static_maps"),
            ScoreModifier(micro=70, mystiko=15, macro=-40),
        )
        self.assertEqual(
            self._option(SET_D, "Q7", "three_way_synergy"),
            ScoreModifier(micro=35, macro=35, mystiko=35),
        )

    def test_registry_version_is_pinned(self):
        for definition in ALL_SETS:
            self.assertEqual(definition.version, REGISTRY_VERSION)
        self.assertEqual(REGISTRY_VERSION, "v1.0.0")


class HybridAssemblerTests(SimpleTestCase):
    def test_true_aesthetics_use_the_dominant_set_for_both_parts(self):
        for category in (
            AestheticCategory.SENSORY,
            AestheticCategory.FANTASY,
            AestheticCategory.NARRATIVE,
            AestheticCategory.CHALLENGE,
        ):
            with self.subTest(category=category):
                definition = REGISTRY_MAP[category]
                assembled = assemble_questionnaire(
                    resolve_aesthetic(category, category)
                )
                self.assertEqual(assembled.version, REGISTRY_VERSION)
                self.assertTrue(assembled.is_true_aesthetic)
                self.assertEqual(assembled.dominant_aesthetic, category.value)
                self.assertIsNone(assembled.secondary_aesthetic)
                self.assertEqual(
                    [n.id for n in assembled.part1_challenge_nodes],
                    [n.id for n in definition.part1_questions],
                )
                self.assertEqual(
                    [n.id for n in assembled.part2_reward_nodes],
                    [n.id for n in definition.part2_questions],
                )

    def test_permutation_matrix_covers_all_sixteen_aesthetics(self):
        canonical = (
            AestheticCategory.SENSORY,
            AestheticCategory.FANTASY,
            AestheticCategory.NARRATIVE,
            AestheticCategory.CHALLENGE,
        )
        tested = 0
        for cat1, cat2 in product(canonical, repeat=2):
            tested += 1
            with self.subTest(cat1=cat1, cat2=cat2):
                resolution = resolve_aesthetic(cat1, cat2)
                assembled = assemble_questionnaire(resolution)
                dominant_def = REGISTRY_MAP[cat1]

                self.assertEqual(
                    _distinct_root_ids(assembled.part1_challenge_nodes),
                    PART1_ROOT_IDS,
                )
                self.assertEqual(
                    [n.id for n in assembled.part1_challenge_nodes],
                    [n.id for n in dominant_def.part1_questions],
                )

                if cat1 == cat2:
                    self.assertTrue(assembled.is_true_aesthetic)
                    self.assertEqual(
                        [n.id for n in assembled.part2_reward_nodes],
                        [n.id for n in dominant_def.part2_questions],
                    )
                else:
                    self.assertFalse(assembled.is_true_aesthetic)
                    secondary_def = REGISTRY_MAP[cat2]
                    roots = _distinct_root_ids(assembled.part2_reward_nodes)
                    self.assertEqual(roots, PART2_ROOT_IDS)
                    self.assertEqual(
                        roots[:3],
                        sorted(SECONDARY_PART2_ROOTS, key=PART2_ROOT_IDS.index),
                    )
                    self.assertEqual(
                        roots[3:],
                        sorted(DOMINANT_PART2_ROOTS, key=PART2_ROOT_IDS.index),
                    )
                    expected_ids = [
                        node.id
                        for node in secondary_def.part2_questions
                        if node.root_id in SECONDARY_PART2_ROOTS
                    ] + [
                        node.id
                        for node in dominant_def.part2_questions
                        if node.root_id in DOMINANT_PART2_ROOTS
                    ]
                    self.assertEqual(
                        [n.id for n in assembled.part2_reward_nodes],
                        expected_ids,
                    )
        self.assertEqual(tested, 16)

    def test_hybrid_keeps_child_branches_with_their_roots(self):
        assembled = assemble_questionnaire(
            resolve_aesthetic(AestheticCategory.SENSORY, AestheticCategory.FANTASY)
        )
        # Q9A comes from Fantasy (SET_B), Q13A/Q13B from Sensory (SET_A).
        q9a = _node_by_id(assembled.part2_reward_nodes, "Q9A")
        self.assertEqual(q9a.text, "How do you prefer to acquire them?")
        self.assertIn("Q13A", [n.id for n in assembled.part2_reward_nodes])
        self.assertIn("Q13B", [n.id for n in assembled.part2_reward_nodes])
        self.assertNotIn("Q11B", [n.id for n in assembled.part2_reward_nodes])

    def test_special_flow_cannot_be_assembled(self):
        resolution = resolve_aesthetic(
            AestheticCategory.COLLABORATIVE, AestheticCategory.NONE
        )
        with self.assertRaises(QuestionnaireRegistryError):
            assemble_questionnaire(resolution)

    def test_assembled_questionnaire_type(self):
        assembled = assemble_questionnaire(
            resolve_aesthetic(AestheticCategory.CHALLENGE, AestheticCategory.NARRATIVE)
        )
        self.assertIsInstance(assembled, AssembledQuestionnaire)
        self.assertEqual(assembled.dominant_aesthetic, "CHALLENGE")
        self.assertEqual(assembled.secondary_aesthetic, "NARRATIVE")


class _PublishedGameMixin(TestCase):
    def _published_game(self, name: str = "Registry Test Game") -> Game:
        return Game.objects.create(
            name=name,
            slug=name.lower().replace(" ", "-"),
            source_type=SourceType.MANUAL,
            content_type="game",
            listing_status="published",
        )

    def _post(self, body: dict):
        return self.client.post(
            ASSEMBLE_URL,
            data=json.dumps(body),
            content_type="application/json",
        )


class AssembleTreeEndpointTests(_PublishedGameMixin):
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

    def test_true_aesthetic_tree(self):
        game = self._published_game()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_C1",
                "q2_option_id": "OPT_NONE",
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["version"], "v1.0.0")
        self.assertEqual(body["game_slug"], game.slug)
        self.assertEqual(body["dominant_aesthetic"], "CHALLENGE")
        self.assertIsNone(body["secondary_aesthetic"])
        self.assertTrue(body["is_true_aesthetic"])
        self.assertEqual(
            _payload_root_ids(body["part1_challenge_nodes"]), PART1_ROOT_IDS
        )
        self.assertEqual(_payload_root_ids(body["part2_reward_nodes"]), PART2_ROOT_IDS)
        first = body["part1_challenge_nodes"][0]
        self.assertEqual(first["id"], "Q3")
        self.assertEqual(first["target"], "CHALLENGE")
        self.assertTrue(first["options"][0]["id"].startswith("Q3_"))
        self.assertIn("modifiers", first["options"][0])
        self.assertIn("next_question_id", first["options"][0])

    def test_hybrid_tree_splits_part2_three_and_three(self):
        game = self._published_game()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_S1",
                "q2_option_id": "OPT_F1",
            }
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["dominant_aesthetic"], "SENSORY")
        self.assertEqual(body["secondary_aesthetic"], "FANTASY")
        self.assertFalse(body["is_true_aesthetic"])

        part2_ids = [node["id"] for node in body["part2_reward_nodes"]]
        # Fantasy (secondary) owns Q9-Q11; Sensory (dominant) owns Q12-Q14.
        self.assertEqual(_payload_root_ids(body["part2_reward_nodes"]), PART2_ROOT_IDS)
        q9a = next(n for n in body["part2_reward_nodes"] if n["id"] == "Q9A")
        self.assertEqual(q9a["text"], "How do you prefer to acquire them?")
        self.assertIn("Q13B", part2_ids)
        self.assertNotIn("Q11B", part2_ids)

    def test_invalid_options_return_422(self):
        game = self._published_game()
        response = self._post(
            {
                "game_slug": game.slug,
                "q1_option_id": "OPT_NONE",
                "q2_option_id": "OPT_S1",
            }
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
