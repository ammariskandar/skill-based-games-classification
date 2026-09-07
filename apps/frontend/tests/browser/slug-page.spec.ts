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
 *   - The Similar Games scaffold renders a heading + exactly 4 skeleton cards.
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

test("submit classification button is inert with integration hooks", async ({
  page,
}) => {
  await page.goto("/dev/slug-page");
  const button = page.locator("#submit-classification-btn");
  await button.waitFor();

  await expect(button).toHaveAttribute("type", "button");
  await expect(button).toHaveAttribute("data-game-slug", "fixture-game");
  await expect(button).toHaveText("Submit Classification");

  // SBGC-220 scope: no modal markup or dialog is mounted for this button.
  const hasModal = await page.evaluate(() => {
    const btn = document.getElementById("submit-classification-btn");
    if (!btn) return true;
    return Boolean(
      document.querySelector("#submit-classification-modal") ??
      btn.querySelector("dialog"),
    );
  });
  expect(hasModal).toBe(false);
});

test("similar games scaffold renders heading and four skeleton cards", async ({
  page,
}) => {
  await page.goto("/dev/slug-page");

  await expect(
    page.getByRole("heading", { name: "Similar Games" }),
  ).toBeVisible();

  await expect(page.locator("[data-similar-games-card]")).toHaveCount(4);
});
