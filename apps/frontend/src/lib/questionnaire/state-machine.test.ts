/**
 * Questionnaire state-machine tests — SBGC-178.
 *
 * Option ids are resolved from the SET_A registry by node + index so the suite
 * survives copywriting changes (option ids derive from their labels).
 */

import { describe, expect, it } from "vitest";

import { SET_A } from "./registry/v1/set-a";
import { QuestionnaireStateMachine } from "./state-machine";
import type { StateMachineEvent } from "./state-machine";

/** Option id of the Nth choice on a SET_A node. */
function optionId(nodeId: string, index: number): string {
  const node =
    SET_A.part1Questions.find((candidate) => candidate.id === nodeId) ??
    SET_A.part2Questions.find((candidate) => candidate.id === nodeId);
  const option = node?.options[index];
  if (option === undefined) throw new Error(`no option #${index} on ${nodeId}`);
  return option.id;
}

function machineWithSensoryTree(): QuestionnaireStateMachine {
  const machine = new QuestionnaireStateMachine();
  machine.setAestheticAnswers("OPT_S1", "OPT_NONE"); // true Sensory → Set A
  return machine;
}

function sequenceIds(machine: QuestionnaireStateMachine): string[] {
  return machine.getActiveSequence().map((node) => node.id);
}

describe("QuestionnaireStateMachine — aesthetics", () => {
  it("assembles the tree from Q1/Q2 selections", () => {
    const machine = machineWithSensoryTree();
    expect(machine.isAssembled).toBe(true);
    expect(machine.dominantAesthetic).toBe("SENSORY");
    expect(machine.isTrueAesthetic).toBe(true);
    expect(sequenceIds(machine)).toContain("Q3");
    expect(sequenceIds(machine)).toContain("Q14");
  });
});

describe("QuestionnaireStateMachine — branching", () => {
  it("inserts a branch node directly after its triggering root", () => {
    const machine = machineWithSensoryTree();
    const before = sequenceIds(machine);
    expect(before).not.toContain("Q4A");

    machine.recordAnswer("Q4", optionId("Q4", 0)); // "Yes" → Q4A
    const after = sequenceIds(machine);
    expect(after[after.indexOf("Q4") + 1]).toBe("Q4A");
  });

  it("prunes the branch and its downstream answers when deselected", () => {
    const machine = machineWithSensoryTree();
    machine.recordAnswer("Q4", optionId("Q4", 0));
    machine.recordAnswer("Q4A", optionId("Q4A", 0));
    expect(machine.answerFor("Q4A")).toBe(optionId("Q4A", 0));

    machine.recordAnswer("Q4", optionId("Q4", 1)); // "No" → Q4B
    expect(sequenceIds(machine)).not.toContain("Q4A");
    expect(machine.answerFor("Q4A")).toBeUndefined();
    expect(sequenceIds(machine)).toContain("Q4B");
  });

  it("removes an answer and prunes the branch it had opened", () => {
    const machine = machineWithSensoryTree();
    machine.recordAnswer("Q4", optionId("Q4", 0));
    machine.recordAnswer("Q4A", optionId("Q4A", 0));

    machine.removeAnswer("Q4");
    expect(machine.answerFor("Q4")).toBeUndefined();
    expect(machine.answerFor("Q4A")).toBeUndefined();
    expect(sequenceIds(machine)).not.toContain("Q4A");
  });
});

describe("QuestionnaireStateMachine — scoring", () => {
  it("updates challenge scores without touching reward scores", () => {
    const machine = machineWithSensoryTree();
    const rewardBefore = { ...machine.reward.raw };

    machine.recordAnswer("Q3", optionId("Q3", 0)); // micro +20 (Challenge)
    expect(machine.challenge.raw.micro).toBe(20);
    expect(machine.reward.raw).toEqual(rewardBefore);
    expect(
      machine.challenge.norm.micro +
        machine.challenge.norm.macro +
        machine.challenge.norm.mystiko,
    ).toBe(100);
  });
});

describe("QuestionnaireStateMachine — events", () => {
  it("fires boundary-swap when transitioning from challenge to reward", () => {
    const machine = machineWithSensoryTree();
    const events: StateMachineEvent[] = [];
    machine.subscribe((event) => events.push(event));

    machine.recordAnswer("Q3", optionId("Q3", 0));
    expect(events.some((event) => event.type === "boundary-swap")).toBe(false);

    machine.recordAnswer("Q9", optionId("Q9", 0)); // first Reward answer
    expect(events.some((event) => event.type === "boundary-swap")).toBe(true);
    expect(events.some((event) => event.type === "reward-update")).toBe(true);
  });
});

describe("QuestionnaireStateMachine — Q15 compensation", () => {
  it("preserves the 100-point total after an adjustment", () => {
    const machine = machineWithSensoryTree();
    machine.recordAnswer("Q3", optionId("Q3", 2)); // micro +10
    machine.recordAnswer("Q5", optionId("Q5", 0)); // mystiko +10
    machine.recordAnswer("Q6", optionId("Q6", 2)); // micro +20

    const norm = { ...machine.challenge.norm };
    machine.adjustScore("CHALLENGE", "micro", norm.micro + 5);

    const adj = machine.challenge.adj;
    expect(adj.micro + adj.macro + adj.mystiko).toBe(100);
    expect(adj.micro).toBe(norm.micro + 5);
  });
});

describe("QuestionnaireStateMachine — payload", () => {
  it("emits the exact wire DTO", () => {
    const machine = machineWithSensoryTree();
    machine.recordAnswer("Q3", optionId("Q3", 0));

    const payload = machine.getPayload("OVERWRITE");
    expect(payload.version).toBe("v1.0.0");
    expect(payload.q1_option_id).toBe("OPT_S1");
    expect(payload.q2_option_id).toBe("OPT_NONE");
    expect(payload.q15_rating).toBe(7);
    expect(payload.answers["Q3"]).toBe(optionId("Q3", 0));
    expect(payload.adjusted_challenge).toEqual(machine.challenge.adj);
    expect(payload.adjusted_reward).toEqual(machine.reward.adj);
    expect(payload.conflict_resolution).toBe("OVERWRITE");
  });

  it("rejects payload generation before aesthetic selection", () => {
    const machine = new QuestionnaireStateMachine();
    expect(() => machine.getPayload()).toThrow();
  });
});

describe("QuestionnaireStateMachine — draft hydration (SBGC-180)", () => {
  function withDraftMeta(
    state: ReturnType<QuestionnaireStateMachine["toDraft"]>,
  ) {
    return { ...state, version: "v1.0.0", updatedAt: Date.now() };
  }

  it("is clean before any choice and dirty once Q1 is chosen", () => {
    const machine = new QuestionnaireStateMachine();
    expect(machine.isDirty()).toBe(false);
    machine.setAestheticAnswers("OPT_S1", "OPT_NONE");
    expect(machine.isDirty()).toBe(true);
  });

  it("round-trips through toDraft/hydrateFromDraft", () => {
    const source = machineWithSensoryTree();
    source.recordAnswer("Q3", optionId("Q3", 0));
    source.recordAnswer("Q4", optionId("Q4", 0));
    source.q15Rating = 9;

    const restored = new QuestionnaireStateMachine();
    expect(restored.hydrateFromDraft(withDraftMeta(source.toDraft("hk")))).toBe(
      true,
    );
    expect(restored.dominantAesthetic).toBe("SENSORY");
    expect(restored.answerFor("Q3")).toBe(optionId("Q3", 0));
    expect(restored.answerFor("Q4")).toBe(optionId("Q4", 0));
    expect(restored.q15Rating).toBe(9);
    expect(restored.challenge.adj).toEqual(source.challenge.adj);
  });

  it("drops answer ids that are not in the active registry tree", () => {
    const source = machineWithSensoryTree();
    source.recordAnswer("Q3", optionId("Q3", 0));
    const draft = withDraftMeta(source.toDraft("hk"));
    draft.answers.Q99 = "does-not-exist";

    const restored = new QuestionnaireStateMachine();
    expect(restored.hydrateFromDraft(draft)).toBe(true);
    expect(restored.answerFor("Q99")).toBeUndefined();
    expect(restored.answerFor("Q3")).toBe(optionId("Q3", 0));
  });

  it("reset clears progress and returns to a clean aesthetics state", () => {
    const machine = machineWithSensoryTree();
    machine.recordAnswer("Q3", optionId("Q3", 0));
    machine.reset();
    expect(machine.phase).toBe("aesthetics");
    expect(machine.isAssembled).toBe(false);
    expect(machine.isDirty()).toBe(false);
  });
});
