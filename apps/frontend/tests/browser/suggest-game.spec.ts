import { expect, test } from "@playwright/test";

/**
 * SBGC-240: the /about game-suggestion modal.
 *
 * The auth gate, the live character counters, and the 429 cooldown are all
 * client behaviour, so they are exercised here on the real page with the two
 * BFF endpoints intercepted — no Django, no session, no network.
 */

const AUTH_STATUS = "**/api/auth/status";
const SUGGESTIONS = "**/api/suggestions";

async function stubAuth(
  page: import("@playwright/test").Page,
  authenticated: boolean,
) {
  await page.route(AUTH_STATUS, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated,
        username: authenticated ? "x" : null,
      }),
    }),
  );
}

test.describe("suggest-a-game modal", () => {
  test("sends an unauthenticated visitor to login with a return path", async ({
    page,
  }) => {
    await stubAuth(page, false);
    await page.goto("/about");

    await page.locator("#open-suggestion-modal-btn").click();

    // SBGC-241: the return path carries the deep link, so login lands the
    // visitor back on /about with the dialog already opening.
    await expect(page).toHaveURL(
      /\/login\?redirect=%2Fabout%3Faction%3Dsuggest$/,
    );
  });

  test("opens for an authenticated visitor and counts characters", async ({
    page,
  }) => {
    await stubAuth(page, true);
    await page.goto("/about");

    await page.locator("#open-suggestion-modal-btn").click();

    const dialog = page.locator("#suggest-game-modal");
    await expect(dialog).toBeVisible();

    await dialog.locator("[data-suggest-name]").fill("Blue Prince");
    await dialog.locator("[data-suggest-remarks]").fill("Puzzle roguelike");

    await expect(dialog.locator('[data-suggest-count="name"]')).toHaveText(
      "11",
    );
    await expect(dialog.locator('[data-suggest-count="remarks"]')).toHaveText(
      "16",
    );
  });

  test("shows the success confirmation on a 200", async ({ page }) => {
    await stubAuth(page, true);
    await page.route(SUGGESTIONS, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, message: "ok" }),
      }),
    );
    await page.goto("/about");

    await page.locator("#open-suggestion-modal-btn").click();
    const dialog = page.locator("#suggest-game-modal");
    await dialog.locator("[data-suggest-name]").fill("Blue Prince");
    await dialog.locator("[data-suggest-submit]").click();

    await expect(dialog.locator("[data-suggest-success]")).toBeVisible();
    await expect(dialog.locator("[data-suggest-form]")).toBeHidden();
  });

  test("starts a countdown from the 429 Retry-After window", async ({
    page,
  }) => {
    await stubAuth(page, true);
    await page.route(SUGGESTIONS, (route) =>
      route.fulfill({
        status: 429,
        headers: { "Retry-After": "30" },
        contentType: "application/json",
        body: JSON.stringify({
          error: { code: "RATE_LIMITED", message: "Please wait 30 seconds." },
        }),
      }),
    );
    await page.goto("/about");

    await page.locator("#open-suggestion-modal-btn").click();
    const dialog = page.locator("#suggest-game-modal");
    await dialog.locator("[data-suggest-name]").fill("Blue Prince");
    await dialog.locator("[data-suggest-submit]").click();

    await expect(dialog.locator("[data-suggest-error]")).toContainText(
      "Please wait 30 seconds.",
    );

    const submit = dialog.locator("[data-suggest-submit]");
    await expect(submit).toBeDisabled();
    await expect(submit).toHaveText(/Submit \(Wait \d+s\)/);

    const until = await page.evaluate(() =>
      sessionStorage.getItem("suggestion_cooldown_until"),
    );
    expect(Number(until)).toBeGreaterThan(Date.now());
  });

  test("the storefront helper keeps a space before the bold protocol", async ({
    page,
  }) => {
    await stubAuth(page, true);
    await page.goto("/about");
    await page.locator("#open-suggestion-modal-btn").click();

    // SBGC-241: the newline between the helper text and the protocol used to be
    // collapsed away, rendering "must start withhttps://".
    await expect(page.locator("#suggest-game-url + p")).toHaveText(
      "0 / 250 — must start with https://",
    );
    await expect(page.locator("#suggest-game-url + p strong")).toHaveText(
      "https://",
    );
  });

  test("the ?action=suggest deep link opens the dialog for a signed-in visitor", async ({
    page,
  }) => {
    await stubAuth(page, true);
    await page.goto("/about?action=suggest");

    await expect(page.locator("#suggest-game-modal")).toBeVisible();
  });

  test("the deep link opens once and leaves close bindings intact", async ({
    page,
  }) => {
    await stubAuth(page, true);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));

    await page.goto("/about?action=suggest");
    const dialog = page.locator("#suggest-game-modal");
    await expect(dialog).toBeVisible();

    // A concurrent second open must not raise InvalidStateError from showModal.
    await page.locator("#open-suggestion-modal-btn").click({ force: true });
    await expect(dialog).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    expect(errors).toEqual([]);
  });

  test("an unauthenticated deep link preserves intent through login", async ({
    page,
  }) => {
    await stubAuth(page, false);
    await page.goto("/about?action=suggest");

    await expect(page).toHaveURL(
      /\/login\?redirect=%2Fabout%3Faction%3Dsuggest$/,
    );
  });

  test("login returns the visitor to a same-origin return path", async ({
    page,
  }) => {
    await stubAuth(page, true);
    await page.route("**/api/auth/login", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ authenticated: true, username: "fixture" }),
      }),
    );

    await page.goto("/login?redirect=%2Fabout%3Faction%3Dsuggest");
    await page.locator("#username").fill("fixture");
    await page.locator("#password").fill("pw");
    await page.locator("#login-submit").click();

    // Lands on the requested page, where the deep link then opens the dialog.
    await expect(page).toHaveURL(/\/about\?action=suggest$/);
    await expect(page.locator("#suggest-game-modal")).toBeVisible();
  });
});
