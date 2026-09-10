/**
 * Versioned questionnaire registry — universal schema (v1.0.0) — SBGC-173.
 *
 * Mirrors `apps/backend/classifications/questionnaire/registry/v1/types.py`
 * exactly.  Sets A–D are declared in `set-a.ts` … `set-d.ts`; the hybrid
 * assembler lives in `assembler.ts`.
 *
 * Pure data + pure construction/validation helpers only.
 */

export const REGISTRY_VERSION = "v1.0.0";

export type Dimension = "micro" | "macro" | "mystiko";
export type ProfileTarget = "CHALLENGE" | "REWARD";

export interface ScoreModifier {
  micro: number;
  macro: number;
  mystiko: number;
}

export interface AnswerOption {
  id: string;
  text: string;
  modifiers: ScoreModifier;
  nextQuestionId: string | null;
}

export interface QuestionNode {
  id: string;
  rootId: string;
  text: string;
  target: ProfileTarget;
  options: AnswerOption[];
  isBranch: boolean;
  parentId: string | null;
  helperText: string | null;
}

export interface QuestionSetDefinition {
  version: string;
  setId: "A" | "B" | "C" | "D";
  name: "Sensory" | "Fantasy" | "Narrative" | "Challenge";
  part1Questions: QuestionNode[];
  part2Questions: QuestionNode[];
}

export interface AssembledQuestionnaire {
  version: string;
  dominantAesthetic: string;
  secondaryAesthetic: string | null;
  isTrueAesthetic: boolean;
  part1ChallengeNodes: QuestionNode[];
  part2RewardNodes: QuestionNode[];
}

export class QuestionRegistryError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QuestionRegistryError";
  }
}

// ═══ construction helpers (used by the set modules) ═══

interface OptionSpec {
  label: string;
  modifiers: ScoreModifier;
  nextQuestionId: string | null;
}

export interface OptParams {
  micro?: number;
  macro?: number;
  mystiko?: number;
  next?: string;
}

/** Declare an answer option with μ (micro), M (macro), κ (mystiko) deltas. */
export function opt(label: string, params: OptParams = {}): OptionSpec {
  return {
    label,
    modifiers: {
      micro: params.micro ?? 0,
      macro: params.macro ?? 0,
      mystiko: params.mystiko ?? 0,
    },
    nextQuestionId: params.next ?? null,
  };
}

const ROOT_ID_RE = /^(Q\d+)/;

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export interface QuestionParams {
  target: ProfileTarget;
  parentId?: string;
  helperText?: string;
}

/** Build a `QuestionNode`, deriving root/branch identity from `nodeId`. */
export function question(
  nodeId: string,
  text: string,
  options: OptionSpec[],
  params: QuestionParams,
): QuestionNode {
  const match = ROOT_ID_RE.exec(nodeId);
  if (match === null) {
    throw new QuestionRegistryError(
      `Question id '${nodeId}' has no root (Q<number>).`,
    );
  }
  const rootId = match[1];
  const isBranch = nodeId !== rootId;
  return {
    id: nodeId,
    rootId,
    text,
    target: params.target,
    options: options.map((spec) => ({
      id: `${nodeId}_${slugify(spec.label)}`,
      text: spec.label,
      modifiers: spec.modifiers,
      nextQuestionId: spec.nextQuestionId,
    })),
    isBranch,
    parentId: params.parentId ?? (isBranch ? rootId : null),
    helperText: params.helperText ?? null,
  };
}

/** Assemble and structurally validate one `QuestionSetDefinition`. */
export function buildSet(
  setId: QuestionSetDefinition["setId"],
  name: QuestionSetDefinition["name"],
  part1: QuestionNode[],
  part2: QuestionNode[],
  version: string = REGISTRY_VERSION,
): QuestionSetDefinition {
  const definition: QuestionSetDefinition = {
    version,
    setId,
    name,
    part1Questions: part1,
    part2Questions: part2,
  };
  validateQuestionSet(definition);
  return definition;
}

// ═══ structural validation ═══

/** Throw `QuestionRegistryError` if `definition` violates an invariant. */
export function validateQuestionSet(definition: QuestionSetDefinition): void {
  const errors: string[] = [];
  validatePart(definition.part1Questions, "CHALLENGE", errors);
  validatePart(definition.part2Questions, "REWARD", errors);
  if (errors.length > 0) {
    throw new QuestionRegistryError(
      `Question set ${definition.setId} (${definition.version}) is invalid: ${errors.join("; ")}`,
    );
  }
}

function validatePart(
  nodes: QuestionNode[],
  expectedTarget: ProfileTarget,
  errors: string[],
): void {
  const byId = new Map<string, QuestionNode>();
  for (const node of nodes) {
    if (byId.has(node.id)) errors.push(`duplicate node id '${node.id}'`);
    byId.set(node.id, node);
    if (node.target !== expectedTarget) {
      errors.push(
        `node '${node.id}' target ${node.target} != ${expectedTarget}`,
      );
    }
    if (node.options.length === 0)
      errors.push(`node '${node.id}' has no options`);
  }

  const roots = nodes.filter((node) => !node.isBranch);
  if (roots.length !== 6) {
    errors.push(`expected 6 ${expectedTarget} roots, found ${roots.length}`);
  }

  for (const node of nodes) {
    for (const option of node.options) {
      if (option.nextQuestionId === null) continue;
      const target = byId.get(option.nextQuestionId);
      if (target === undefined) {
        errors.push(
          `node '${node.id}' option '${option.id}' points to unknown '${option.nextQuestionId}'`,
        );
      } else if (target.target !== expectedTarget) {
        errors.push(
          `node '${node.id}' option '${option.id}' crosses profiles into '${option.nextQuestionId}'`,
        );
      }
    }
  }

  const reachable = reachableFromRoots(roots, byId);
  for (const node of nodes) {
    if (node.isBranch && !reachable.has(node.id)) {
      errors.push(`branch node '${node.id}' is unreachable from any root`);
    }
  }

  const cycle = findCycle(roots, byId);
  if (cycle !== null) {
    errors.push(`branch cycle detected: ${cycle.join(" -> ")}`);
  }
}

function reachableFromRoots(
  roots: QuestionNode[],
  byId: Map<string, QuestionNode>,
): Set<string> {
  const seen = new Set<string>();
  const stack = roots.map((node) => node.id);
  while (stack.length > 0) {
    const current = stack.pop() as string;
    if (seen.has(current)) continue;
    seen.add(current);
    const node = byId.get(current);
    if (node === undefined) continue;
    for (const option of node.options) {
      if (option.nextQuestionId !== null) stack.push(option.nextQuestionId);
    }
  }
  return seen;
}

function findCycle(
  roots: QuestionNode[],
  byId: Map<string, QuestionNode>,
): string[] | null {
  const state = new Map<string, "visiting" | "done">();
  const path: string[] = [];

  const visit = (nodeId: string): string[] | null => {
    state.set(nodeId, "visiting");
    path.push(nodeId);
    const node = byId.get(nodeId);
    if (node !== undefined) {
      for (const option of node.options) {
        const target = option.nextQuestionId;
        if (target === null) continue;
        const targetState = state.get(target);
        if (targetState === "visiting") {
          return [...path.slice(path.indexOf(target)), target];
        }
        if (targetState === undefined) {
          const found = visit(target);
          if (found !== null) return found;
        }
      }
    }
    path.pop();
    state.set(nodeId, "done");
    return null;
  };

  for (const root of roots) {
    if (!state.has(root.id)) {
      const found = visit(root.id);
      if (found !== null) return found;
    }
  }
  return null;
}
