import { expect, test, type Page } from "@playwright/test";

/**
 * SBGC-194: the Game-detail artwork column must use intrinsic (rem-based)
 * sizing so browser zoom scales it, instead of a viewport-fraction (`fr`)
 * that keeps it at roughly the same physical size under zoom.
 *
 * The fixture page (`/dev/game-detail`) mirrors the `/games/[slug]` grid.
 */

function artworkWidth(page: Page): Promise<number | null> {
  return page.evaluate(() => {
    const el = document.querySelector<HTMLElement>("[data-artwork]");
    return el ? el.getBoundingClientRect().width : null;
  });
}

test("game-detail artwork column is intrinsic rem sizing", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/dev/game-detail");
  await page.locator("[data-artwork]").waitFor();

  const widthAt1280 = await artworkWidth(page);

  // 1024px CSS viewport ≈ 125% browser zoom on a 1280px display. The `lg`
  // breakpoint still applies, so the two-column layout holds.
  await page.setViewportSize({ width: 1024, height: 800 });
  const widthAt1024 = await artworkWidth(page);

  expect(widthAt1280).not.toBeNull();
  expect(widthAt1024).not.toBeNull();

  // A fixed 44rem column keeps the artwork's CSS width constant regardless of
  // viewport width — the property that makes browser zoom scale it physically.
  expect(widthAt1024!).toBeCloseTo(widthAt1280!, 0);
  // 44rem = 704px at the default 16px root.
  expect(widthAt1024!).toBeGreaterThan(690);
  expect(widthAt1024!).toBeLessThan(720);
});
