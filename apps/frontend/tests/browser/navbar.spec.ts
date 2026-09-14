import { expect, test, type Page } from "@playwright/test";

/**
 * SBGC-226: sticky navbar & z-index elevation.
 *
 * Exercises the real site header on the `/dev/navbar` fixture (no Django
 * backend) at a mobile viewport: sticky persistence while scrolling, the named
 * stacking hierarchy, mobile drawer scroll-locking, and native top-layer modals.
 */

test.use({ viewport: { width: 375, height: 667 } });

async function headerTop(page: Page): Promise<number> {
  return page
    .locator("[data-header]")
    .evaluate((el) => el.getBoundingClientRect().y);
}

test("navbar stays pinned to the top while scrolling", async ({ page }) => {
  await page.goto("/dev/navbar");

  const header = page.locator("[data-header]");
  await expect(header).toBeVisible();
  expect(Math.abs(await headerTop(page))).toBeLessThanOrEqual(1);

  await page.evaluate(() => window.scrollTo(0, 800));
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeGreaterThanOrEqual(799);

  expect(Math.abs(await headerTop(page))).toBeLessThanOrEqual(1);
  await expect(header).toBeInViewport();
});

test("navbar is sticky and sits above sticky page insets", async ({ page }) => {
  await page.goto("/dev/navbar");

  const header = page.locator("[data-header]");
  const inset = page.locator("[data-sticky-inset]");

  await expect(header).toHaveCSS("position", "sticky");
  await expect(header).toHaveCSS("z-index", "40");
  await expect(inset).toHaveCSS("position", "sticky");
  await expect(inset).toHaveCSS("z-index", "20");

  // The hamburger stays interactive at scroll depth.
  await page.evaluate(() => window.scrollTo(0, 1400));
  const hamburger = page.locator("#nav-disclosure summary");
  await expect(hamburger).toBeVisible();
  await hamburger.click();
  await expect(page.locator("#nav-panel")).toBeVisible();
});

test("mobile drawer locks background scroll and releases on outside click", async ({
  page,
}) => {
  await page.goto("/dev/navbar");

  await page.click("#nav-disclosure summary");
  await expect(page.locator("#nav-panel")).toBeVisible();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe(
    "hidden",
  );

  // Click far below the drawer panel, outside the disclosure.
  await page.mouse.click(4, 640);
  await expect(page.locator("#nav-panel")).not.toBeVisible();
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("");
});

test("native modals render in the top layer above the sticky navbar", async ({
  page,
}) => {
  await page.goto("/dev/navbar");

  const header = page.locator("[data-header]");
  await expect(header).toHaveCSS("z-index", "40");

  await page.click("#fixture-dialog-open");
  const dialog = page.locator("#fixture-dialog");
  await expect(dialog).toBeVisible();
  // The top layer is independent of the z-index scale, so the dialog always
  // paints above the navbar without needing a higher numeric layer.
  expect(await dialog.evaluate((el) => el.matches(":modal"))).toBe(true);
  await expect(header).toHaveCSS("z-index", "40");
});
