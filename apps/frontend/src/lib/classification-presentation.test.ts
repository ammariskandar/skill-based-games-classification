/**
 * Presentation-only classification tests (SBGC-73).
 *
 * These prove the locked Micro/Macro/Mystiko order and the null/non-ready/
 * ready state narrowing. No Django arithmetic is invoked.
 */

import { describe, expect, it, vi } from "vitest";

import {
  CLASSIFICATION_DIMENSION_ORDER,
  dominantBadgeHtml,
  dominantForProfile,
  presentClassification,
  profileDimensions,
} from "./classification-presentation";
import type { GameFinalClassification } from "./server/api/games";

describe("profileDimensions", () => {
  it("returns the locked Micro/Macro/Mystiko order", () => {
    expect(CLASSIFICATION_DIMENSION_ORDER).toEqual([
      "micro",
      "macro",
      "mystiko",
    ]);
  });

  it("maps asymmetric values to the correct dimensions", () => {
    const dimensions = profileDimensions({ micro: 51, macro: 31, mystiko: 18 });

    expect(dimensions).toEqual([
      { key: "micro", label: "Micro", value: 51 },
      { key: "macro", label: "Macro", value: 31 },
      { key: "mystiko", label: "Mystiko", value: 18 },
    ]);
  });
});

describe("dominantForProfile", () => {
  it("returns the strictly-highest Challenge dimension", () => {
    expect(
      dominantForProfile(
        "challenge",
        { micro: 51, macro: 31, mystiko: 18 },
        null,
      ),
    ).toBe("micro");
    expect(
      dominantForProfile(
        "challenge",
        { micro: 20, macro: 70, mystiko: 10 },
        null,
      ),
    ).toBe("macro");
    expect(
      dominantForProfile(
        "challenge",
        { micro: 20, macro: 10, mystiko: 70 },
        null,
      ),
    ).toBe("mystiko");
  });

  it("returns null for a Challenge tie (no strict winner)", () => {
    expect(
      dominantForProfile(
        "challenge",
        { micro: 50, macro: 50, mystiko: 0 },
        null,
      ),
    ).toBeNull();
  });

  it("returns the strictly-highest Reward dimension", () => {
    expect(
      dominantForProfile("reward", null, { micro: 13, macro: 27, mystiko: 60 }),
    ).toBe("mystiko");
    expect(
      dominantForProfile("reward", null, { micro: 80, macro: 10, mystiko: 10 }),
    ).toBe("micro");
  });

  it("derives the Unified dominant from summed Challenge + Reward", () => {
    // Challenge is macro-dominant, Reward is mystiko-dominant; the summed
    // Unified vector is mystiko-dominant (mirrors SBGC-81 unified dominance).
    const challenge = { micro: 40, macro: 50, mystiko: 10 };
    const reward = { micro: 10, macro: 20, mystiko: 70 };
    expect(dominantForProfile("unified", challenge, reward)).toBe("mystiko");
  });

  it("returns null for a Unified tie", () => {
    const challenge = { micro: 70, macro: 10, mystiko: 20 };
    const reward = { micro: 10, macro: 70, mystiko: 20 };
    expect(dominantForProfile("unified", challenge, reward)).toBeNull();
  });

  it("returns null when required vectors are missing", () => {
    expect(dominantForProfile("challenge", null, null)).toBeNull();
    expect(dominantForProfile("reward", null, null)).toBeNull();
    expect(dominantForProfile("unified", null, null)).toBeNull();
    expect(
      dominantForProfile(
        "unified",
        { micro: 50, macro: 30, mystiko: 20 },
        null,
      ),
    ).toBeNull();
  });
});

describe("dominantBadgeHtml", () => {
  it("renders a dimension-colored badge for a known dominant", () => {
    const html = dominantBadgeHtml("mystiko", true);
    expect(html).toContain("rankings-detail__dominant-badge");
    expect(html).toContain("rankings-detail__dominant-badge--mystiko");
    expect(html).toContain("Dominant: Mystiko");
  });

  it("renders the truthful unclassified empty state", () => {
    expect(dominantBadgeHtml(null, false)).toContain("Not yet classified");
    expect(dominantBadgeHtml(null, false)).not.toContain("dominant-badge--");
  });

  it("renders the tie empty state without fabricating a dimension", () => {
    expect(dominantBadgeHtml(null, true)).toContain("No dominant dimension");
  });
});

describe("presentClassification", () => {
  it("treats a null classification as unavailable", () => {
    expect(presentClassification(null)).toEqual({ kind: "unavailable" });
  });

  it("treats a missing profile as unavailable (non-ready)", () => {
    const classification: GameFinalClassification = {
      status: "NO_SUBMISSIONS",
      regime: "none",
      challenge: null,
      reward: null,
      confidence_level: null,
      confidence_label: null,
      submission_count: 0,
      calculation_version: null,
      calculated_at: null,
      is_stale: false,
    };
    expect(presentClassification(classification)).toEqual({
      kind: "unavailable",
    });
  });

  it("returns a ready state with scores, confidence, regime, and stale flag", () => {
    const classification: GameFinalClassification = {
      status: "READY",
      regime: "provisional",
      challenge: { micro: 51, macro: 31, mystiko: 18 },
      reward: { micro: 13, macro: 27, mystiko: 60 },
      confidence_level: 82,
      confidence_label: "High",
      submission_count: 42,
      calculation_version: "STATISTICAL_MODEL_V1.0.0",
      calculated_at: "2026-08-21T00:00:00Z",
      is_stale: false,
    };

    const presentation = presentClassification(classification);

    expect(presentation.kind).toBe("ready");
    if (presentation.kind === "ready") {
      expect(presentation.challenge.micro).toBe(51);
      expect(presentation.challenge.macro).toBe(31);
      expect(presentation.challenge.mystiko).toBe(18);
      expect(presentation.reward.micro).toBe(13);
      expect(presentation.reward.macro).toBe(27);
      expect(presentation.reward.mystiko).toBe(60);
      expect(presentation.confidence).toBe(82);
      expect(presentation.confidenceLabel).toBe("High");
      expect(presentation.regime).toBe("provisional");
      expect(presentation.isStale).toBe(false);
      expect(presentation.submissionCount).toBe(42);
    }
  });

  it("preserves a stale flag alongside valid scores", () => {
    const classification: GameFinalClassification = {
      status: "READY",
      regime: "unified",
      challenge: { micro: 40, macro: 35, mystiko: 25 },
      reward: { micro: 20, macro: 30, mystiko: 50 },
      confidence_level: 72.1,
      confidence_label: "Medium",
      submission_count: 30,
      calculation_version: "STATISTICAL_MODEL_V1.0.0",
      calculated_at: "2026-08-20T00:00:00Z",
      is_stale: true,
    };

    const presentation = presentClassification(classification);

    expect(presentation.kind).toBe("ready");
    if (presentation.kind === "ready") {
      expect(presentation.regime).toBe("unified");
      expect(presentation.isStale).toBe(true);
      expect(presentation.challenge.micro).toBe(40);
    }
  });
});

describe("presentClassification — malformed profile validation", () => {
  it("fails closed when the reward profile is malformed", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const presentation = presentClassification({
      status: "READY",
      regime: "provisional",
      challenge: { micro: 50, macro: 30, mystiko: 20 },
      reward: { micro: 60, macro: 40, mystiko: 40 }, // sums to 140
      confidence_level: 80,
      confidence_label: "High",
      submission_count: 10,
      calculation_version: null,
      calculated_at: null,
      is_stale: false,
    });

    expect(presentation).toEqual({ kind: "unavailable" });
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it("fails closed when the challenge profile is malformed", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const presentation = presentClassification({
      status: "READY",
      challenge: { micro: -5, macro: 60, mystiko: 45 },
      reward: { micro: 50, macro: 30, mystiko: 20 },
    });

    expect(presentation).toEqual({ kind: "unavailable" });
    warn.mockRestore();
  });

  it("fails closed on non-object input", () => {
    expect(presentClassification("not-a-classification")).toEqual({
      kind: "unavailable",
    });
  });

  it("fails closed when one profile is missing", () => {
    const presentation = presentClassification({
      status: "READY",
      challenge: { micro: 50, macro: 30, mystiko: 20 },
      reward: null,
    });

    expect(presentation).toEqual({ kind: "unavailable" });
  });
});
