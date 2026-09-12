import { expect, test, type Page } from "@playwright/test";

/**
 * SBGC-225: manual score submission flow.
 *
 * Exercises the real `GameDetailBody` on the `/dev/slug-page` fixture (no Django
 * backend). The BFF endpoints are mocked at the HTTP boundary:
 *
 *   GET  /api/auth/status                              → auth gate (SBGC-217)
 *   GET  /api/questionnaire/{slug}/session             → submission pre-check
 *   POST /api/classifications/games/{slug}/submit-score → SBGC-216 outcome
 */

const AUTH_URL = "**/api/auth/status";
const SESSION_URL = "**/api/questionnaire/*/session";
const SUBMIT_URL = "**/api/classifications/games/*/submit-score";

const NO_PREVIOUS = {
  game_slug: "fixture-game",
  game_name: "Fixture Game",
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

const WITH_PREVIOUS = {
  ...NO_PREVIOUS,
  previous_result: {
    result_id: 3,
    version: "v1.0.0",
    dominant_aesthetic: "SENSORY",
    secondary_aesthetic: "FANTASY",
    is_true_aesthetic: false,
    q15_rating: 8,
    adjusted_challenge: { micro: 55, macro: 25, mystiko: 20 },
    adjusted_reward: { micro: 30, macro: 40, mystiko: 30 },
    status: "ACTIVE_IN_CALCULATION",
    created_at: "2026-09-01T00:00:00Z",
  },
};

const WITH_MANUAL = {
  ...NO_PREVIOUS,
  precedence: {
    has_conflict: true,
    requires_user_choice: false,
    manual_submission_id: 12,
    manual_created_at: "2026-09-11T00:00:00Z",
    age_days: 0,
  },
};

function submitBody(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: 12,
    game_slug: "fixture-game",
    aesthetic: "SENSORY",
    secondary_aesthetic: "FANTASY",
    is_duplicate: false,
    is_updated: false,
    is_created: true,
    submitted_at: "2026-09-11T00:00:00Z",
    ...overrides,
  };
}

async function mockAuth(page: Page, authenticated = true): Promise<void> {
  await page.route(AUTH_URL, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated,
        username: authenticated ? "tester" : null,
      }),
    }),
  );
}

async function mockSession(
  page: Page,
  body: unknown,
  status = 200,
): Promise<void> {
  await page.route(SESSION_URL, (route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

async function mockSubmit(
  page: Page,
  body: unknown,
  status = 200,
): Promise<void> {
  await page.route(SUBMIT_URL, (route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

async function openModal(
  page: Page,
  options: { session?: unknown; authenticated?: boolean } = {},
): Promise<void> {
  const { session = NO_PREVIOUS, authenticated = true } = options;
  await mockAuth(page, authenticated);
  await mockSession(page, session);
  await page.goto("/dev/slug-page");
  await page.click("#submit-classification-btn");
}

async function openManualForm(page: Page): Promise<void> {
  await openModal(page);
  await page.click("[data-submission-skip]");
}

async function selectAesthetic(page: Page, value = "SENSORY"): Promise<void> {
  await page.selectOption("[data-aesthetic-select]", value);
}

async function selectSecondaryAesthetic(
  page: Page,
  value = "FANTASY",
): Promise<void> {
  await page.selectOption("[data-secondary-aesthetic-select]", value);
}

async function fillValidScores(page: Page): Promise<void> {
  await page
    .locator('input[data-profile="challenge"][data-dimension="micro"]')
    .fill("100");
  await page
    .locator('input[data-profile="reward"][data-dimension="micro"]')
    .fill("100");
  await selectAesthetic(page);
  await selectSecondaryAesthetic(page);
}

test("glow button opens the dialog and traps focus", async ({ page }) => {
  await mockAuth(page);
  await mockSession(page, NO_PREVIOUS);
  await page.goto("/dev/slug-page");
  await page.locator("#submit-classification-btn").waitFor();

  await page.click("#submit-classification-btn");
  await expect(page.locator("#score-submission-modal")).toBeVisible();

  const focusedInDialog = await page.evaluate(() => {
    const dialog = document.getElementById("score-submission-modal");
    return dialog !== null && dialog.contains(document.activeElement);
  });
  expect(focusedInDialog).toBe(true);

  const centred = await page.evaluate(() => {
    const dialog = document.getElementById("score-submission-modal")!;
    const rect = dialog.getBoundingClientRect();
    const dx = Math.abs(rect.x + rect.width / 2 - window.innerWidth / 2);
    const dy = Math.abs(rect.y + rect.height / 2 - window.innerHeight / 2);
    return dx < 4 && dy < 4;
  });
  expect(centred).toBe(true);
});

test("unauthenticated users see the login prompt", async ({ page }) => {
  await openModal(page, { authenticated: false });

  const unauth = page.locator('[data-submission-state="unauthenticated"]');
  await expect(unauth).toBeVisible();
  await expect(unauth).toContainText("Please log in to submit a score");
  await expect(unauth.locator('a[href*="/login"]')).toBeVisible();
});

test("authenticated users see the choice prompt and can skip to manual", async ({
  page,
}) => {
  await openModal(page);

  const choice = page.locator('[data-submission-state="choice"]');
  await expect(choice).toBeVisible();
  await expect(choice).toContainText("Guided Score Builder");
  await expect(choice).toContainText(
    "Fine-tune your ratings in a few quick steps.",
  );
  await expect(
    choice.locator('img[src="/icons/recommendationengineicon.png"]'),
  ).toHaveJSProperty("naturalWidth", 512);
  await page.click("[data-submission-skip]");
  await expect(page.locator('[data-submission-state="manual"]')).toBeVisible();
  await expect(page.locator("[data-manual-score-form]")).toBeVisible();
});

test("a failed session fetch renders an honest error state", async ({
  page,
}) => {
  await mockAuth(page);
  await mockSession(page, { error: "boom" }, 500);
  await page.goto("/dev/slug-page");
  await page.click("#submit-classification-btn");

  const error = page.locator('[data-submission-state="session-error"]');
  await expect(error).toBeVisible();
  await expect(error).toContainText("couldn't load your submission status");
  await expect(error.locator("[data-session-retry]")).toBeVisible();
});

test("returning users see the server-reported already-submitted state", async ({
  page,
}) => {
  await openModal(page, { session: WITH_MANUAL });

  const submitted = page.locator('[data-submission-state="submitted"]');
  await expect(submitted).toBeVisible();
  await expect(submitted).toContainText(
    "You already submitted a classification score",
  );
  await expect(submitted.locator("[data-submitted-age]")).toHaveText("today");

  await page.click("[data-submitted-continue]");
  await expect(page.locator('[data-submission-state="manual"]')).toBeVisible();
});

test("existing questionnaire shows the overwrite interstitial", async ({
  page,
}) => {
  await openModal(page, { session: WITH_PREVIOUS });

  const overwrite = page.locator('[data-submission-state="overwrite"]');
  await expect(overwrite).toBeVisible();
  await expect(overwrite).toContainText("Existing Assessment Found");
  await expect(
    overwrite.locator('[data-overwrite="challenge.micro"]'),
  ).toHaveText("55");
  await expect(overwrite.locator('[data-overwrite="reward.macro"]')).toHaveText(
    "40",
  );

  await page.click("[data-overwrite-proceed]");
  await expect(page.locator('[data-submission-state="manual"]')).toBeVisible();
  await expect(page.locator("[data-manual-score-form]")).toBeVisible();
});

test("cancelling the overwrite interstitial keeps the previous record", async ({
  page,
}) => {
  await openModal(page, { session: WITH_PREVIOUS });
  await page.click("[data-overwrite-cancel]");
  await expect(page.locator("#score-submission-modal")).not.toBeVisible();
});

test("enlarged modal and UI element dimensions", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openManualForm(page);

  const dialogWidth = await page
    .locator("#score-submission-modal")
    .evaluate((el) => el.getBoundingClientRect().width);
  expect(dialogWidth).toBeGreaterThanOrEqual(800);

  const stepper = page
    .locator(
      'button[data-step="inc"][data-profile="challenge"][data-dimension="micro"]',
    )
    .first();
  const box = await stepper.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThanOrEqual(40);
  expect(box!.height).toBeGreaterThanOrEqual(40);
});

test("native number spinners are suppressed", async ({ page }) => {
  await openManualForm(page);

  const appearance = await page
    .locator('input[data-profile="challenge"][data-dimension="micro"]')
    .evaluate((el) => getComputedStyle(el).appearance);
  expect(appearance).toBe("textfield");
});

test("stepper buttons adjust dimension values", async ({ page }) => {
  await openManualForm(page);

  const input = page.locator(
    'input[data-profile="challenge"][data-dimension="micro"]',
  );
  const inc = page.locator(
    'button[data-step="inc"][data-profile="challenge"][data-dimension="micro"]',
  );

  await inc.click();
  await expect(input).toHaveValue("1");
  await inc.click();
  await expect(input).toHaveValue("2");
});

test("submit stays disabled until both panels total 100 and an aesthetic is chosen", async ({
  page,
}) => {
  await openManualForm(page);

  const submit = page.locator("[data-submit-scores]");
  await expect(submit).toBeDisabled();

  await page
    .locator('input[data-profile="challenge"][data-dimension="micro"]')
    .fill("100");
  await page
    .locator('input[data-profile="reward"][data-dimension="micro"]')
    .fill("100");
  await expect(submit).toBeDisabled();

  await selectAesthetic(page);
  await expect(submit).toBeEnabled();
});

test("secondary aesthetic cannot repeat the primary", async ({ page }) => {
  await openManualForm(page);

  const secondary = page.locator("[data-secondary-aesthetic-select]");
  await expect(secondary).toHaveValue("");

  await selectAesthetic(page, "SENSORY");
  await expect(secondary.locator('option[value="SENSORY"]')).toBeDisabled();

  await selectSecondaryAesthetic(page, "FANTASY");
  await expect(secondary).toHaveValue("FANTASY");

  await selectAesthetic(page, "FANTASY");
  await expect(secondary).toHaveValue("");
});

test("aesthetic tooltip toggles aria-expanded on activation", async ({
  page,
}) => {
  await openManualForm(page);

  const trigger = page.locator("[data-aesthetic-tooltip-trigger]");
  const panel = page.locator("[data-aesthetic-tooltip-panel]");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(panel).toBeHidden();

  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Sensory");

  await page.keyboard.press("Escape");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await expect(panel).toBeHidden();
});

test("a first-time submission (201) shows the success result", async ({
  page,
}) => {
  await openManualForm(page);
  await mockSubmit(page, submitBody(), 201);
  await fillValidScores(page);
  await page.click("[data-submit-scores]");

  const result = page.locator('[data-submission-state="result"]');
  await expect(result).toBeVisible();
  await expect(result).toContainText("Classification Submitted Successfully!");
  await expect(
    result.locator('[data-result-score="challenge.micro"]'),
  ).toHaveText("100");
});

test("a <15-day resubmission (200 updated) shows the updated result", async ({
  page,
}) => {
  await openManualForm(page);
  await mockSubmit(
    page,
    submitBody({ is_created: false, is_updated: true }),
    200,
  );
  await fillValidScores(page);
  await page.click("[data-submit-scores]");

  const result = page.locator('[data-submission-state="result"]');
  await expect(result).toBeVisible();
  await expect(result).toContainText("Score UPDATED!");
});

test("a chained duplicate shows the confirmed result", async ({ page }) => {
  await openManualForm(page);
  await mockSubmit(
    page,
    submitBody({ is_created: false, is_updated: false, is_duplicate: true }),
    200,
  );
  await fillValidScores(page);
  await page.click("[data-submit-scores]");

  const result = page.locator('[data-submission-state="result"]');
  await expect(result).toBeVisible();
  await expect(result).toContainText("Score Confirmed (Duplicate Ignored)");
});

test("a server error shows the error notice and retains entered values", async ({
  page,
}) => {
  await openManualForm(page);
  await mockSubmit(
    page,
    {
      error: {
        code: "SUBMISSION_FAILED",
        message: "Internal submission error.",
      },
    },
    500,
  );
  await fillValidScores(page);
  await page.click("[data-submit-scores]");

  const result = page.locator('[data-submission-state="result"]');
  await expect(result).toBeVisible();
  await expect(result.locator("[data-result-error]")).toBeVisible();
  await expect(result.locator("[data-result-error]")).toContainText(
    "Internal submission error.",
  );

  await page.click("[data-result-back]");
  await expect(page.locator('[data-submission-state="manual"]')).toBeVisible();
  await expect(
    page.locator('input[data-profile="challenge"][data-dimension="micro"]'),
  ).toHaveValue("100");
});

test("re-opening after a submission reflects the server state", async ({
  page,
}) => {
  await openManualForm(page);
  await mockSubmit(page, submitBody(), 201);
  await fillValidScores(page);
  await page.click("[data-submit-scores]");
  await expect(page.locator('[data-submission-state="result"]')).toBeVisible();
  await page.click("[data-submission-close]");

  // The server now reports an existing manual submission.
  await page.unroute(SESSION_URL);
  await mockSession(page, WITH_MANUAL);
  await page.click("#submit-classification-btn");

  await expect(
    page.locator('[data-submission-state="submitted"]'),
  ).toBeVisible();
});
