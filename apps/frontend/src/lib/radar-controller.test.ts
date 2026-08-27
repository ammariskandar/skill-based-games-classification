import { describe, expect, it } from "vitest";

import { prefersReducedMotion } from "./radar-controller";
import {
  buildRadarDescription,
  buildRadarSummaryRows,
  buildRadarTitle,
  buildVertexAriaLabel,
  buildVertexLabel,
  type SkillProfileVector,
} from "./skill-dimensions";

describe("prefersReducedMotion", () => {
  it("is true when the media query matches reduce", () => {
    expect(prefersReducedMotion(() => ({ matches: true }))).toBe(true);
  });

  it("is false when the media query does not match reduce", () => {
    expect(prefersReducedMotion(() => ({ matches: false }))).toBe(false);
  });
});

describe("buildRadarTitle", () => {
  it("includes the game title when provided", () => {
    expect(buildRadarTitle("Portal 2")).toBe(
      "Portal 2 Skill Classification Radar",
    );
  });

  it("falls back to a generic title", () => {
    expect(buildRadarTitle()).toBe("Skill Classification Radar Chart");
  });
});

describe("buildRadarDescription", () => {
  const challenge: SkillProfileVector = { micro: 60, mystiko: 20, macro: 20 };
  const reward: SkillProfileVector = { micro: 30, mystiko: 40, macro: 30 };

  it("describes both complete profiles", () => {
    const description = buildRadarDescription(challenge, reward);
    expect(description).toContain(
      "Challenge profile (Micro: 60, Mystiko: 20, Macro: 20)",
    );
    expect(description).toContain(
      "Reward profile (Micro: 30, Mystiko: 40, Macro: 30)",
    );
  });

  it("describes a partial profile set", () => {
    const description = buildRadarDescription(challenge, null);
    expect(description).toContain("Challenge profile");
    expect(description).not.toContain("Reward profile");
  });

  it("describes an empty profile set", () => {
    const description = buildRadarDescription(null, null);
    expect(description).toContain("no available skill classification profiles");
  });
});

describe("buildRadarSummaryRows", () => {
  const challenge: SkillProfileVector = { micro: 10, mystiko: 20, macro: 70 };
  const reward: SkillProfileVector = { micro: 40, mystiko: 30, macro: 30 };

  it("returns exact numeric rows for both profiles", () => {
    const rows = buildRadarSummaryRows(challenge, reward);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      profile: "challenge",
      label: "Challenge",
      micro: 10,
      mystiko: 20,
      macro: 70,
    });
    expect(rows[1]).toMatchObject({
      profile: "reward",
      label: "Reward",
      micro: 40,
      mystiko: 30,
      macro: 30,
    });
  });

  it("omits null profiles", () => {
    const rows = buildRadarSummaryRows(challenge, null);
    expect(rows).toHaveLength(1);
    expect(rows[0].profile).toBe("challenge");
  });
});

describe("buildVertexLabel / buildVertexAriaLabel", () => {
  it("builds the profile-dimension label", () => {
    expect(buildVertexLabel("challenge", "micro")).toBe("Challenge Micro");
    expect(buildVertexLabel("reward", "mystiko")).toBe("Reward Mystiko");
  });

  it("builds an aria-label that includes the score", () => {
    expect(buildVertexAriaLabel("challenge", "micro", 45)).toBe(
      "Challenge Micro: 45",
    );
  });
});
