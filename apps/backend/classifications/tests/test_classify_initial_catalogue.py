"""
``classify_initial_catalogue`` command tests — SBGC-128.

Covers fixture integrity (count, slug parity, 100-point sums, canonical
aesthetics), opinionated provenance (every stored profile is recomputed from the
recorded questionnaire answers by the real scoring engine), dry-run safety,
idempotent ingestion, and the missing-submitter guard.  No network access
anywhere.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from games.models import ContentType, Game, ListingStatus, SourceType

from classifications.models import AESTHETIC_CHOICES, EditorialClassification
from classifications.questionnaire.aesthetic_resolver import resolve_aesthetic
from classifications.questionnaire.domain import AestheticCategory
from classifications.questionnaire.registry.v1.assembler import assemble_questionnaire
from classifications.questionnaire.registry.v1.types import (
    REGISTRY_VERSION,
    ProfileTarget,
    QuestionNode,
)
from classifications.questionnaire.scoring.engine import (
    compute_raw_profile,
    normalize_profile,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = BACKEND_ROOT / "games" / "fixtures" / "initial_catalogue_200.json"
FIXTURE_PATH = (
    BACKEND_ROOT / "classifications" / "fixtures" / "initial_classifications_200.json"
)

MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

DIMENSIONS = ("micro", "mystiko", "macro")
CANONICAL_AESTHETICS = {value for value, _label in AESTHETIC_CHOICES}
SUBMITTER = "timunlessteh"


# ---------------------------------------------------------------------------
# Instrument recomputation helpers
# ---------------------------------------------------------------------------


def _assembled_for(entry: dict):
    """Assemble the questionnaire the game's aesthetic pair dispatches to."""
    resolution = resolve_aesthetic(
        AestheticCategory(entry["primary_aesthetic"]),
        AestheticCategory(entry["secondary_aesthetic"]),
    )
    return assemble_questionnaire(resolution)


def _walk(nodes: tuple[QuestionNode, ...], indexes: dict, label: str) -> dict[str, str]:
    """Resolve ``{node_id: option_index}`` into ``{node_id: option_id}``.

    The walk follows every root and the branch chain its selected options route
    to, so a missing answer, an out-of-range index, or an answer for a node the
    path never reaches fails loudly instead of being silently ignored.
    """
    by_id = {node.id: node for node in nodes}
    resolved: dict[str, str] = {}
    for root in [node for node in nodes if not node.is_branch]:
        node: QuestionNode | None = root
        while node is not None:
            assert node.id in indexes, f"{label}: no answer for {node.id}"
            index = indexes[node.id]
            assert isinstance(index, int) and not isinstance(index, bool), (
                f"{label}: {node.id} index is not an int"
            )
            assert 0 <= index < len(node.options), (
                f"{label}: {node.id} index {index} out of range"
            )
            option = node.options[index]
            resolved[node.id] = option.id
            node = by_id[option.next_question_id] if option.next_question_id else None

    assert set(resolved) == set(indexes), (
        f"{label}: answers do not match the answered path "
        f"(unused: {sorted(set(indexes) - set(resolved))})"
    )
    return resolved


def _recomputed_profile(entry: dict, answers_key: str, target: ProfileTarget) -> dict:
    """Recompute one profile from the fixture's recorded answers."""
    assembled = _assembled_for(entry)
    nodes = (
        assembled.part1_challenge_nodes
        if target is ProfileTarget.CHALLENGE
        else assembled.part2_reward_nodes
    )
    answers = _walk(nodes, entry[answers_key], f"{entry['slug']}.{answers_key}")
    normalized = normalize_profile(compute_raw_profile(answers, nodes, target))
    return {
        "micro": normalized.micro,
        "mystiko": normalized.mystiko,
        "macro": normalized.macro,
    }


# ---------------------------------------------------------------------------
# Fixture integrity — no database
# ---------------------------------------------------------------------------


class FixtureIntegrityTests(SimpleTestCase):
    def test_exactly_200_entries(self):
        self.assertEqual(len(FIXTURE), 200)

    def test_slug_parity_with_the_game_manifest(self):
        fixture_slugs = [entry["slug"] for entry in FIXTURE]
        manifest_slugs = {entry["slug"] for entry in MANIFEST}

        self.assertEqual(len(set(fixture_slugs)), 200, "duplicate slugs in the fixture")
        self.assertEqual(set(fixture_slugs), manifest_slugs)

    def test_every_profile_is_integers_totalling_exactly_100(self):
        for entry in FIXTURE:
            for key in ("challenge_profile", "reward_profile"):
                profile = entry[key]
                self.assertEqual(set(profile), set(DIMENSIONS), entry["slug"])
                for dimension in DIMENSIONS:
                    value = profile[dimension]
                    self.assertIsInstance(
                        value, int, f"{entry['slug']}.{key}.{dimension}"
                    )
                    self.assertNotIsInstance(value, bool)
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(value, 100)
                self.assertEqual(sum(profile.values()), 100, f"{entry['slug']}.{key}")

    def test_aesthetics_match_the_manifest_and_are_canonical(self):
        manifest_by_slug = {entry["slug"]: entry for entry in MANIFEST}
        for entry in FIXTURE:
            source = manifest_by_slug[entry["slug"]]
            self.assertEqual(entry["primary_aesthetic"], source["primary_aesthetic"])
            self.assertEqual(
                entry["secondary_aesthetic"], source["secondary_aesthetic"]
            )
            self.assertIn(entry["primary_aesthetic"], CANONICAL_AESTHETICS)
            self.assertIn(entry["secondary_aesthetic"], CANONICAL_AESTHETICS)

    def test_intended_dominant_is_a_canonical_dimension(self):
        """The curation label is recorded for provenance and reported against.

        It is deliberately *not* asserted to lead either profile: the SBGC-128
        course-correction makes the questionnaire instrument authoritative, so a
        divergence is a documented finding rather than a fixture defect.
        """
        for entry in FIXTURE:
            self.assertIn(entry["intended_dominant"], DIMENSIONS, entry["slug"])

    def test_every_game_is_a_hybrid_aesthetic_pair(self):
        for entry in FIXTURE:
            self.assertNotEqual(
                entry["primary_aesthetic"],
                entry["secondary_aesthetic"],
                entry["slug"],
            )

    def test_registry_version_matches_the_checked_in_registry(self):
        for entry in FIXTURE:
            self.assertEqual(entry["registry_version"], REGISTRY_VERSION, entry["slug"])

    def test_profiles_recompute_exactly_from_recorded_answers(self):
        """The stored vectors are derived, not hand-written.

        Each vector is recomputed from the fixture's own ``challenge_answers`` /
        ``reward_answers`` through the canonical engine: assemble the game's
        hybrid questionnaire, resolve the answer path, accumulate raw dimension
        points, and normalize to a 100-point distribution.
        """
        for entry in FIXTURE:
            self.assertEqual(
                entry["challenge_profile"],
                _recomputed_profile(
                    entry, "challenge_answers", ProfileTarget.CHALLENGE
                ),
                f"{entry['slug']} challenge profile",
            )
            self.assertEqual(
                entry["reward_profile"],
                _recomputed_profile(entry, "reward_answers", ProfileTarget.REWARD),
                f"{entry['slug']} reward profile",
            )

    def test_every_entry_carries_a_rationale(self):
        for entry in FIXTURE:
            self.assertTrue(entry["rationale"].strip(), entry["slug"])


# ---------------------------------------------------------------------------
# Command behaviour — database-backed
# ---------------------------------------------------------------------------


def _seed_games() -> None:
    Game.objects.bulk_create(
        Game(
            source_type=SourceType.MANUAL,
            external_id=None,
            name=entry["name"],
            slug=entry["slug"],
            content_type=ContentType.GAME,
            listing_status=ListingStatus.PUBLISHED,
        )
        for entry in MANIFEST
    )


class CommandTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username=SUBMITTER, password="pw")
        _seed_games()


class DryRunTests(CommandTestCase):
    def test_dry_run_writes_nothing(self):
        out = StringIO()
        call_command("classify_initial_catalogue", "--dry-run", stdout=out)

        self.assertEqual(EditorialClassification.objects.count(), 0)
        self.assertIn("Would create: 200", out.getvalue())
        self.assertIn("nothing written", out.getvalue())

    def test_dry_run_reports_update_for_an_existing_submission(self):
        call_command("classify_initial_catalogue", stdout=StringIO())

        out = StringIO()
        call_command("classify_initial_catalogue", "--dry-run", stdout=out)

        self.assertIn("Would update: 200", out.getvalue())
        self.assertEqual(EditorialClassification.objects.count(), 200)


class IngestTests(CommandTestCase):
    def test_ingest_creates_one_submission_per_game(self):
        out = StringIO()
        call_command("classify_initial_catalogue", stdout=out)

        self.assertEqual(EditorialClassification.objects.count(), 200)
        self.assertIn("Created: 200", out.getvalue())

    def test_ingest_maps_profiles_aesthetics_and_rationale(self):
        call_command("classify_initial_catalogue", stdout=StringIO())

        entry = next(item for item in FIXTURE if item["slug"] == "celeste")
        submission = EditorialClassification.objects.get(game__slug="celeste")

        self.assertEqual(submission.submitted_by, self.user)
        self.assertEqual(submission.updated_by, self.user)
        self.assertEqual(submission.aesthetic, entry["primary_aesthetic"])
        self.assertEqual(submission.secondary_aesthetic, entry["secondary_aesthetic"])
        self.assertEqual(submission.notes, entry["rationale"])
        self.assertEqual(
            submission.challenge_profile.micro_score,
            entry["challenge_profile"]["micro"],
        )
        self.assertEqual(
            submission.reward_profile.macro_score, entry["reward_profile"]["macro"]
        )

    def test_second_run_updates_in_place_and_duplicates_nothing(self):
        call_command("classify_initial_catalogue", stdout=StringIO())
        first_ids = set(EditorialClassification.objects.values_list("id", flat=True))

        out = StringIO()
        call_command("classify_initial_catalogue", stdout=out)

        self.assertEqual(EditorialClassification.objects.count(), 200)
        self.assertEqual(
            set(EditorialClassification.objects.values_list("id", flat=True)), first_ids
        )
        self.assertIn("Created: 0", out.getvalue())
        self.assertIn("Updated: 200", out.getvalue())

    def test_rerun_restores_a_drifted_profile(self):
        call_command("classify_initial_catalogue", stdout=StringIO())

        submission = EditorialClassification.objects.get(game__slug="celeste")
        profile = submission.challenge_profile
        profile.micro_score, profile.mystiko_score, profile.macro_score = 34, 33, 33
        profile.save()

        call_command("classify_initial_catalogue", stdout=StringIO())

        profile.refresh_from_db()
        expected = next(e for e in FIXTURE if e["slug"] == "celeste")[
            "challenge_profile"
        ]
        self.assertEqual(profile.micro_score, expected["micro"])
        self.assertEqual(profile.mystiko_score, expected["mystiko"])
        self.assertEqual(profile.macro_score, expected["macro"])

    def test_another_editors_submission_is_not_matched_or_overwritten(self):
        other = User.objects.create_user(username="someone-else", password="pw")
        game = Game.objects.get(slug="celeste")
        other_submission = EditorialClassification.objects.create(
            game=game, submitted_by=other, updated_by=other
        )

        call_command("classify_initial_catalogue", stdout=StringIO())

        other_submission.refresh_from_db()
        self.assertEqual(EditorialClassification.objects.filter(game=game).count(), 2)
        self.assertIsNone(
            other_submission.aesthetic, "another editor's row must be untouched"
        )
        self.assertTrue(
            EditorialClassification.objects.filter(
                game=game, submitted_by=self.user
            ).exists()
        )

    def test_missing_game_is_skipped_without_aborting_the_batch(self):
        Game.objects.filter(slug="celeste").delete()

        out = StringIO()
        call_command("classify_initial_catalogue", stdout=out)

        self.assertIn("Skipped: 1", out.getvalue())
        self.assertIn("Created: 199", out.getvalue())
        self.assertEqual(EditorialClassification.objects.count(), 199)


class SubmitterTests(TestCase):
    def test_missing_user_is_a_command_error(self):
        _seed_games()

        with self.assertRaises(CommandError):
            call_command(
                "classify_initial_catalogue",
                "--username",
                "nobody-here",
                stdout=StringIO(),
            )

        self.assertEqual(EditorialClassification.objects.count(), 0)

    def test_missing_fixture_is_a_command_error(self):
        User.objects.create_user(username=SUBMITTER, password="pw")

        with self.assertRaises(CommandError):
            call_command(
                "classify_initial_catalogue",
                "--fixture",
                "/nonexistent/fixture.json",
                stdout=StringIO(),
            )
