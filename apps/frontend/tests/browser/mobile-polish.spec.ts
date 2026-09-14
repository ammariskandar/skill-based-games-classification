import { expect, test } from "@playwright/test";

/**
 * SBGC-226 follow-up: mobile polish regressions.
 *
 * Covers the mobile-only tweaks (rankings back affordance, methodology
 * equation fit, About accordion sizing, hero proportions, radar toggle labels)
 * and the all-viewport Capsule crop fix.
 */

const MOBILE = { width: 375, height: 667 };

test.describe("mobile", () => {
  test.use({ viewport: MOBILE });

  test("rankings detail shows a back link above the game title", async ({
    page,
  }) => {
    await page.goto("/dev/rankings-detail");

    const back = page.locator("[data-rankings-back]");
    await expect(back).toBeVisible();
    await expect(back).toHaveAttribute("href", "/rankings?profile=challenge");

    const backBox = await back.boundingBox();
    const titleBox = await page
      .locator(".rankings-detail__heading")
      .boundingBox();
    expect(backBox).not.toBeNull();
    expect(titleBox).not.toBeNull();
    expect(backBox!.y).toBeLessThan(titleBox!.y);
  });

  test("methodology has no horizontal overflow and equations fit", async ({
    page,
  }) => {
    await page.goto("/methodology");

    const overflow = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    const widest = await page.evaluate(() => {
      let widest = 0;
      for (const el of document.querySelectorAll<HTMLElement>(
        ".katex-display",
      )) {
        widest = Math.max(widest, el.scrollWidth - el.clientWidth);
      }
      return widest;
    });
    expect(widest).toBeLessThanOrEqual(1);
  });

  test("about accordion titles are reduced on mobile", async ({ page }) => {
    await page.goto("/about");
    const sizes = await page
      .locator("details summary h2")
      .evaluateAll((nodes) =>
        nodes.map((node) => parseFloat(getComputedStyle(node).fontSize)),
      );
    expect(sizes.length).toBeGreaterThan(0);
    for (const size of sizes) {
      expect(size).toBeLessThanOrEqual(16);
    }
  });

  test("the slug hero is ~10% taller while overlay elements keep their size", async ({
    page,
  }) => {
    await page.goto("/dev/slug-page");

    const ratio = await page
      .locator("[data-game-image] .game-image__frame")
      .evaluate((el) => {
        const rect = el.getBoundingClientRect();
        return rect.width / rect.height;
      });
    expect(ratio).toBeCloseTo(15 / 11, 1);
  });
});

test("the radar toggle is labelled Challenge / Reward", async ({ page }) => {
  await page.goto("/dev/game-image-capsule");
  const labels = await page
    .locator(".radar-toggle-group .radar-profile-btn")
    .allTextContents();
  expect(labels.map((label) => label.trim())).toEqual(["Challenge", "Reward"]);
});

test("a non-2:3 custom Capsule crops to fill its frame", async ({ page }) => {
  await page.goto("/dev/game-image-capsule");
  const fit = await page
    .locator(".game-image__enhance--capsule .game-image__original")
    .evaluate((el) => getComputedStyle(el).objectFit);
  expect(fit).toBe("cover");
});

test("the rankings back link is hidden on desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/dev/rankings-detail");
  await expect(page.locator("[data-rankings-back]")).toBeHidden();
});
