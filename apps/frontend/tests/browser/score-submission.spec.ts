import { expect, test, type Page } from "@playwright/test";

/**
 * SBGC-215: interactive score submission modal.
 *
 * Exercises the real `GameDetailBody` on the `/dev/slug-page` fixture (no Django
 * backend). Auth is driven by the temporary `mock_auth_logged_in` localStorage
 * flag; a missing flag/cookie is the unauthenticated path.
 */

async function openManualForm(page: Page): Promise<void> {
  await page.goto("/dev/slug-page");
  await page.evaluate(() =>
    localStorage.setItem("mock_auth_logged_in", "true"),
  );
  await page.click("#submit-classification-btn");
  await page.click("[data-submission-skip]");
}

async function fillValidScores(page: Page): Promise<void> {
  await page
    .locator('input[data-profile="challenge"][data-dimension="micro"]')
    .fill("100");
  await page
    .locator('input[data-profile="reward"][data-dimension="micro"]')
    .fill("100");
}

test("glow button opens the dialog and traps focus", async ({ page }) => {
  await page.goto("/dev/slug-page");
  await page.locator("#submit-classification-btn").waitFor();

  await page.click("#submit-classification-btn");
  await expect(page.locator("#score-submission-modal")).toBeVisible();

  const focusedInDialog = await page.evaluate(() => {
    const dialog = document.getElementById("score-submission-modal");
    return dialog !== null && dialog.contains(document.activeElement);
  });
  expect(focusedInDialog).toBe(true);

  // The dialog must be centred over the backdrop. (Tailwind preflight zeroes
  // the UA's auto margins, which used to pin it to the top-left.)
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
  await page.goto("/dev/slug-page");
  await page.evaluate(() => localStorage.removeItem("mock_auth_logged_in"));
  await page.click("#submit-classification-btn");

  const unauth = page.locator('[data-submission-state="unauthenticated"]');
  await expect(unauth).toBeVisible();
  await expect(unauth).toContainText("Please log in to submit a score");
  await expect(unauth.locator('a[href*="/login"]')).toBeVisible();
});

test("authenticated users see the choice prompt and can skip to manual", async ({
  page,
}) => {
  await page.goto("/dev/slug-page");
  await page.evaluate(() =>
    localStorage.setItem("mock_auth_logged_in", "true"),
  );
  await page.click("#submit-classification-btn");

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

test("stepper buttons adjust dimension values", async ({ page }) => {
  await openManualForm(page);

  const input = page.locator(
    'input[data-profile="challenge"][data-dimension="micro"]',
  );
  const inc = page.locator(
    'button[data-step="inc"][data-profile="challenge"][data-dimension="micro"]',
  );
  const dec = page.locator(
    'button[data-step="dec"][data-profile="challenge"][data-dimension="micro"]',
  );

  await inc.click();
  await expect(input).toHaveValue("1");
  await inc.click();
  await expect(input).toHaveValue("2");
  await dec.click();
  await expect(input).toHaveValue("1");
});

test("submit stays disabled until both panels total 100", async ({ page }) => {
  await openManualForm(page);

  const submit = page.locator("[data-submit-scores]");
  await expect(submit).toBeDisabled();

  await page
    .locator('input[data-profile="challenge"][data-dimension="micro"]')
    .fill("100");
  await expect(
    page.locator('[data-total][data-profile="challenge"]'),
  ).toHaveText("Total: 100 / 100");
  await expect(submit).toBeDisabled();

  await page
    .locator('input[data-profile="reward"][data-dimension="micro"]')
    .fill("100");
  await expect(submit).toBeEnabled();
});

test("submitting valid scores caches and shows the submitted view", async ({
  page,
}) => {
  await openManualForm(page);
  await fillValidScores(page);
  await page.click("[data-submit-scores]");

  const submitted = page.locator('[data-submission-state="submitted"]');
  await expect(submitted).toBeVisible();
  await expect(submitted).toContainText(
    "You have already submitted a classification score",
  );

  const cached = await page.evaluate(() =>
    localStorage.getItem("mygamedna_submission_fixture-game"),
  );
  expect(cached).not.toBeNull();
  const parsed = JSON.parse(cached!);
  expect(parsed.challenge.micro).toBe(100);
  expect(parsed.reward.micro).toBe(100);
});

test("re-opening the modal shows cached scores without resetting", async ({
  page,
}) => {
  await openManualForm(page);
  await fillValidScores(page);
  await page.click("[data-submit-scores]");

  await page.click("[data-submission-close]");
  await expect(page.locator("#score-submission-modal")).not.toBeVisible();

  await page.click("#submit-classification-btn");
  await expect(
    page.locator('[data-submission-state="submitted"]'),
  ).toBeVisible();
  await expect(page.locator('[data-submitted="challenge.micro"]')).toHaveText(
    "100",
  );
});

test("clearing the cache restores the unsubmitted flow", async ({ page }) => {
  await openManualForm(page);
  await fillValidScores(page);
  await page.click("[data-submit-scores]");
  await page.click("[data-submission-close]");

  await page.evaluate(() =>
    localStorage.removeItem("mygamedna_submission_fixture-game"),
  );

  await page.click("#submit-classification-btn");
  await expect(page.locator('[data-submission-state="choice"]')).toBeVisible();
  await page.click("[data-submission-skip]");
  await expect(
    page.locator('input[data-profile="challenge"][data-dimension="micro"]'),
  ).toHaveValue("0");
});
