"""
Versioned questionnaire registry — universal schema (v1.0.0) — SBGC-173.

Immutable, code-owned data structures for the SBGC-171 questionnaire.  Sets
A–D are Python modules in this package; the frontend mirrors them one-to-one
under ``apps/frontend/src/lib/questionnaire/registry/v1/``.

No Django, ORM, cache, or network imports — this module is pure data and pure
construction/validation helpers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

REGISTRY_VERSION = "v1.0.0"

_ROOT_ID_RE = re.compile(r"^(Q\d+)")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class Dimension(StrEnum):
    """The three classification dimensions."""

    MICRO = "micro"
    MACRO = "macro"
    MYSTIKO = "mystiko"


class ProfileTarget(StrEnum):
    """Which profile a question contributes to."""

    CHALLENGE = "CHALLENGE"
    REWARD = "REWARD"


@dataclass(frozen=True)
class ScoreModifier:
    """Signed per-dimension point delta contributed by one answer option."""

    micro: int = 0
    macro: int = 0
    mystiko: int = 0

    def is_zero(self) -> bool:
        return self.micro == 0 and self.macro == 0 and self.mystiko == 0


@dataclass(frozen=True)
class AnswerOption:
    """One selectable answer and its score delta / branch target."""

    id: str
    text: str
    modifiers: ScoreModifier
    next_question_id: str | None = None


@dataclass(frozen=True)
class QuestionNode:
    """One question: a root (Q3–Q8 / Q9–Q14) or a child branch node."""

    id: str
    root_id: str
    text: str
    target: ProfileTarget
    options: tuple[AnswerOption, ...]
    is_branch: bool = False
    parent_id: str | None = None
    helper_text: str | None = None


@dataclass(frozen=True)
class QuestionSetDefinition:
    """One aesthetic set (A–D): 6 Part 1 roots + 6 Part 2 roots + branches."""

    version: str
    set_id: str
    name: str
    part1_questions: tuple[QuestionNode, ...]
    part2_questions: tuple[QuestionNode, ...]


@dataclass(frozen=True)
class AssembledQuestionnaire:
    """The dispatch contract consumed by SBGC-174 / SBGC-178 / SBGC-179."""

    version: str
    dominant_aesthetic: str
    secondary_aesthetic: str | None
    is_true_aesthetic: bool
    part1_challenge_nodes: tuple[QuestionNode, ...]
    part2_reward_nodes: tuple[QuestionNode, ...]


class QuestionRegistryError(ValueError):
    """Raised when a question set violates a structural invariant."""


# ---------------------------------------------------------------------------
# Construction helpers (used by the set modules)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _OptionSpec:
    """Pre-build option declaration; the id is derived from label + question."""

    label: str
    modifiers: ScoreModifier
    next_question_id: str | None = None


def opt(
    label: str,
    *,
    micro: int = 0,
    macro: int = 0,
    mystiko: int = 0,
    next: str | None = None,
) -> _OptionSpec:
    """Declare an answer option with μ (micro), M (macro), κ (mystiko) deltas."""
    return _OptionSpec(label, ScoreModifier(micro, macro, mystiko), next)


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("_", text.lower()).strip("_")


def question(
    node_id: str,
    text: str,
    options: Iterable[_OptionSpec],
    *,
    target: ProfileTarget,
    parent_id: str | None = None,
    helper_text: str | None = None,
) -> QuestionNode:
    """Build a :class:`QuestionNode`, deriving root/branch identity from *node_id*."""
    match = _ROOT_ID_RE.match(node_id)
    if match is None:
        raise QuestionRegistryError(f"Question id '{node_id}' has no root (Q<number>).")
    root_id = match.group(1)
    is_branch = node_id != root_id
    built = tuple(
        AnswerOption(
            id=f"{node_id}_{_slugify(spec.label)}",
            text=spec.label,
            modifiers=spec.modifiers,
            next_question_id=spec.next_question_id,
        )
        for spec in options
    )
    return QuestionNode(
        id=node_id,
        root_id=root_id,
        text=text,
        target=target,
        options=built,
        is_branch=is_branch,
        parent_id=parent_id or (root_id if is_branch else None),
        helper_text=helper_text,
    )


def build_set(
    set_id: str,
    name: str,
    part1: Iterable[QuestionNode],
    part2: Iterable[QuestionNode],
    *,
    version: str = REGISTRY_VERSION,
) -> QuestionSetDefinition:
    """Assemble and structurally validate one :class:`QuestionSetDefinition`."""
    definition = QuestionSetDefinition(
        version=version,
        set_id=set_id,
        name=name,
        part1_questions=tuple(part1),
        part2_questions=tuple(part2),
    )
    validate_question_set(definition)
    return definition


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def validate_question_set(definition: QuestionSetDefinition) -> None:
    """Raise :class:`QuestionRegistryError` if *definition* is malformed.

    Enforces root cardinality, target integrity, unique ids, branch
    reachability from roots, and acyclicity of the ``next_question_id`` graph.
    """
    errors: list[str] = []
    _validate_part(
        definition,
        definition.part1_questions,
        ProfileTarget.CHALLENGE,
        errors,
    )
    _validate_part(
        definition,
        definition.part2_questions,
        ProfileTarget.REWARD,
        errors,
    )
    if errors:
        joined = "; ".join(errors)
        raise QuestionRegistryError(
            f"Question set {definition.set_id} ({definition.version}) is invalid: "
            f"{joined}"
        )


def _validate_part(
    definition: QuestionSetDefinition,
    nodes: tuple[QuestionNode, ...],
    expected_target: ProfileTarget,
    errors: list[str],
) -> None:
    by_id: dict[str, QuestionNode] = {}
    for node in nodes:
        if node.id in by_id:
            errors.append(f"duplicate node id '{node.id}'")
        by_id[node.id] = node
        if node.target is not expected_target:
            errors.append(f"node '{node.id}' target {node.target} != {expected_target}")
        if not node.options:
            errors.append(f"node '{node.id}' has no options")

    roots = [node for node in nodes if not node.is_branch]
    if len(roots) != 6:
        errors.append(f"expected 6 {expected_target} roots, found {len(roots)}")

    for node in nodes:
        for option in node.options:
            target_id = option.next_question_id
            if target_id is None:
                continue
            target_node = by_id.get(target_id)
            if target_node is None:
                errors.append(
                    f"node '{node.id}' option '{option.id}' points to unknown "
                    f"'{target_id}'"
                )
            elif target_node.target is not expected_target:
                errors.append(
                    f"node '{node.id}' option '{option.id}' crosses profiles "
                    f"into '{target_id}'"
                )

    # Reachability: every branch node must be reachable from a root.
    reachable = _reachable_from_roots(roots, by_id)
    for node in nodes:
        if node.is_branch and node.id not in reachable:
            errors.append(f"branch node '{node.id}' is unreachable from any root")

    # Acyclicity of the branch graph.
    cycle = _find_cycle(roots, by_id)
    if cycle is not None:
        errors.append(f"branch cycle detected: {' -> '.join(cycle)}")
    _ = definition  # definition retained for future set-scoped checks


def _reachable_from_roots(
    roots: list[QuestionNode], by_id: dict[str, QuestionNode]
) -> set[str]:
    seen: set[str] = set()
    stack = [node.id for node in roots]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        node = by_id.get(current)
        if node is None:
            continue
        for option in node.options:
            if option.next_question_id is not None:
                stack.append(option.next_question_id)
    return seen


def _find_cycle(
    roots: list[QuestionNode], by_id: dict[str, QuestionNode]
) -> list[str] | None:
    """Return one cycle path if the branch graph contains a cycle, else None."""
    state: dict[str, int] = {}  # 0 = visiting, 1 = done
    path: list[str] = []

    def visit(node_id: str) -> list[str] | None:
        state[node_id] = 0
        path.append(node_id)
        node = by_id.get(node_id)
        if node is not None:
            for option in node.options:
                target = option.next_question_id
                if target is None:
                    continue
                target_state = state.get(target)
                if target_state == 0:
                    return [*path[path.index(target) :], target]
                if target_state is None:
                    found = visit(target)
                    if found is not None:
                        return found
        path.pop()
        state[node_id] = 1
        return None

    for root in roots:
        if root.id not in state:
            found = visit(root.id)
            if found is not None:
                return found
    return None


__all__ = [
    "REGISTRY_VERSION",
    "AnswerOption",
    "AssembledQuestionnaire",
    "Dimension",
    "ProfileTarget",
    "QuestionNode",
    "QuestionRegistryError",
    "QuestionSetDefinition",
    "ScoreModifier",
    "build_set",
    "opt",
    "question",
    "validate_question_set",
]
