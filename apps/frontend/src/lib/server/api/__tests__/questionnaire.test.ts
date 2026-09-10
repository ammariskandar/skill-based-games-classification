/**
 * Behavioural tests for the questionnaire API boundary (SBGC-176).
 *
 * Every test mocks globalThis.fetch — no real network requests are made.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

function setEnv(value: string) {
  vi.stubEnv("DJANGO_API_URL", value);
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function importQuestionnaire() {
  vi.resetModules();
  return import("../questionnaire");
}

const SESSION = {
  game_slug: "hades",
  game_name: "Hades",
  canonical_aesthetic: null,
  precedence: {
    has_conflict: false,
    requires_user_choice: false,
    manual_submission_id: null,
    manual_created_at: null,
    age_days: null,
  },
  previous_result: null,
};

const SUBMIT_OK = {
  success: true,
  questionnaire_result_id: 7,
  classification_status: "ACTIVE_IN_CALCULATION",
  is_active_in_calculation: true,
  routed_to_editorial: false,
  message: "Questionnaire promoted to active calculation submission.",
  challenge: { micro: 40, macro: 30, mystiko: 30 },
  reward: { micro: 35, macro: 35, mystiko: 30 },
};

const PAYLOAD = {
  version: "v1.0.0",
  q1_option_id: "OPT_S1",
  q2_option_id: "OPT_NONE",
  answers: { Q3: "Q3_huge" },
  q15_rating: 7,
  adjusted_challenge: { micro: 40, macro: 30, mystiko: 30 },
  adjusted_reward: { micro: 35, macro: 35, mystiko: 30 },
};

describe("getQuestionnaireSession", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
  });

  it("returns the parsed session and forwards the session cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(SESSION));
    vi.stubGlobal("fetch", fetchMock);

    const { getQuestionnaireSession } = await importQuestionnaire();
    const session = await getQuestionnaireSession("hades", {
      sessionId: "abc",
    });

    expect(session.game_slug).toBe("hades");
    expect(session.precedence.has_conflict).toBe(false);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://backend.test/api/v1/questionnaire/hades/session");
    expect(init.headers.get("Cookie")).toBe("sessionid=abc");
  });

  it("throws QuestionnaireApiError on a 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "NOT_FOUND",
              message: "Published game 'nope' not found.",
              details: [],
            },
          },
          404,
        ),
      ),
    );

    const { QuestionnaireApiError, getQuestionnaireSession } =
      await importQuestionnaire();
    await expect(getQuestionnaireSession("nope")).rejects.toBeInstanceOf(
      QuestionnaireApiError,
    );
  });
});

describe("submitQuestionnaire", () => {
  beforeEach(() => {
    setEnv("https://backend.test");
  });

  it("returns a success discriminant on 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(SUBMIT_OK, 201));
    vi.stubGlobal("fetch", fetchMock);

    const { submitQuestionnaire } = await importQuestionnaire();
    const result = await submitQuestionnaire("hades", PAYLOAD, {
      sessionId: "abc",
    });

    expect(result.type).toBe("success");
    if (result.type === "success") {
      expect(result.statusCode).toBe(201);
      expect(result.data.questionnaire_result_id).toBe(7);
      expect(result.data.is_active_in_calculation).toBe(true);
    }
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://backend.test/api/v1/questionnaire/hades/submit");
    expect(init.method).toBe("POST");
    expect(init.headers.get("Cookie")).toBe("sessionid=abc");
    expect(init.headers.get("Content-Type")).toBe("application/json");
  });

  it("returns a conflict discriminant on 409", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: "conflict_resolution_required",
            message: "A recent manual submission exists.",
            precedence: {
              has_conflict: true,
              requires_user_choice: true,
              manual_submission_id: 12,
              manual_created_at: "2026-09-07T00:00:00Z",
              age_days: 3,
            },
          },
          409,
        ),
      ),
    );

    const { submitQuestionnaire } = await importQuestionnaire();
    const result = await submitQuestionnaire("hades", PAYLOAD);

    expect(result.type).toBe("conflict");
    if (result.type === "conflict") {
      expect(result.data.error).toBe("conflict_resolution_required");
      expect(result.data.precedence.manual_submission_id).toBe(12);
    }
  });

  it("throws QuestionnaireApiError on a 422", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "VALIDATION_ERROR",
              message: "Adjusted Challenge score deviates too far.",
              details: [],
            },
          },
          422,
        ),
      ),
    );

    const { QuestionnaireApiError, submitQuestionnaire } =
      await importQuestionnaire();
    await expect(submitQuestionnaire("hades", PAYLOAD)).rejects.toBeInstanceOf(
      QuestionnaireApiError,
    );
  });
});
