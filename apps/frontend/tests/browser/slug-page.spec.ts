import { expect, test } from "@playwright/test";

/**
 * SBGC-220: slug-page layout restructure.
 *
 * Structural assertions against the `/dev/slug-page` fixture, which renders the
 * real `GameDetailBody` component with static data (no Django backend). The
 * assertions pin the new layout contract:
 *
 *   - Game Information button follows the hero artwork in document order.
 *   - Skill Classification and Confidence share one grid parent.
 *   - The "Submit Classification" button is inert with its integration hooks.
 *   - The Similar Games section renders ranked cards with a score per card.
 */

test("game information button follows the hero artwork", async ({ page }) => {
  await page.goto("/dev/slug-page");
  await page.locator("[data-game-image]").waitFor();

  const follows = await page.evaluate(() => {
    const art = document.querySelector("[data-game-image]");
    const info = document.querySelector("[data-game-info-trigger]");
    if (!art || !info) return false;
    // Node.DOCUMENT_POSITION_FOLLOWING (4): `info` appears after `art`.
    return (art.compareDocumentPosition(info) & 4) !== 0;
  });

  expect(follows).toBe(true);
  await expect(page.locator(".game-info__trigger-title")).toHaveText(
    "Detailed Game Information",
  );
});

test("confidence percentage is colour-coded", async ({ page }) => {
  await page.goto("/dev/slug-page");
  const value = page.locator(".confidence__value");
  await value.waitFor();

  // The fixture's confidence_level is 87 → the green tier.
  await expect(value).toHaveText("87%");
  await expect(value).toHaveClass(/confidence__value--green/);
});

test("skill classification and confidence share a grid parent", async ({
  page,
}) => {
  await page.goto("/dev/slug-page");
  await page.locator(".classification__grid").waitFor();

  const layout = await page.evaluate(() => {
    const profiles = document.querySelector(".classification__profiles");
    const confidence = document.querySelector(".classification__confidence");
    if (!profiles || !confidence) return null;
    return {
      sameParent: profiles.parentElement === confidence.parentElement,
      parentClass: profiles.parentElement?.className ?? "",
    };
  });

  expect(layout).not.toBeNull();
  expect(layout!.sameParent).toBe(true);
  expect(layout!.parentClass).toContain("classification__grid");
});

test("submit score button is wired to the modal", async ({ page }) => {
  await page.goto("/dev/slug-page");
  const button = page.locator("#submit-classification-btn");
  await button.waitFor();

  await expect(button).toHaveAttribute("type", "button");
  await expect(button).toHaveAttribute("data-game-slug", "fixture-game");
  await expect(button).toHaveAttribute("aria-haspopup", "dialog");
  await expect(button).toHaveAttribute(
    "aria-controls",
    "score-submission-modal",
  );
  await expect(button).toHaveText("Submit a classification score");

  // The dialog it controls is present in the document.
  await expect(page.locator("#score-submission-modal")).toBeAttached();
});

test("similar games renders ranked cards with scores", async ({ page }) => {
  await page.goto("/dev/slug-page");

  await expect(
    page.getByRole("heading", { name: "Similar Games" }),
  ).toBeVisible();

  const cards = page.locator("[data-similar-games-card]");
  await expect(cards).toHaveCount(2);
  await expect(cards.first()).toHaveAttribute("data-similarity-score", "82");
  await expect(page.getByRole("link", { name: "Fixture Ally" })).toBeVisible();
});
