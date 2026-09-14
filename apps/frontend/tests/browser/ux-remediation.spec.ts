import { expect, test } from "@playwright/test";

/**
 * SBGC-241: presentation and revisit-contract regressions.
 *
 * Row geometry and the pagination contract are asserted against the dev fixture
 * `/dev/pagination` (real components, no Django). The legal-page alignment is
 * asserted against the real prerendered pages.
 */

test("ranking rows render a smaller Hero and a denser row", async ({
  page,
}) => {
  await page.goto("/dev/pagination");

  const media = page.locator(".ranking-row__media").first();
  const mediaBox = await media.boundingBox();
  expect(mediaBox).not.toBeNull();

  // 12rem at the default 16px root, down from the 14rem (224px) baseline.
  expect(mediaBox!.width).toBeGreaterThan(188);
  expect(mediaBox!.width).toBeLessThan(196);
  expect(mediaBox!.width).toBeLessThan(224);

  // The frame stays aspect-locked, so the Hero scales rather than letterboxes.
  expect(mediaBox!.width / mediaBox!.height).toBeCloseTo(460 / 215, 1);

  // Row = Hero height + 2 x 0.75rem padding + borders. The SBGC-240 baseline
  // with a 14rem Hero measured ~141px; ~126px is the ~11% denser result.
  const row = page.locator(".ranking-row").first();
  const rowBox = await row.boundingBox();
  expect(rowBox).not.toBeNull();
  expect(rowBox!.height).toBeLessThan(134);
  expect(rowBox!.height).toBeGreaterThan(115);
});

test("pagination links ask the browser to prerender their targets", async ({
  page,
}) => {
  await page.goto("/dev/pagination");

  const scripts = page.locator('script[type="speculationrules"]');
  const count = await scripts.count();
  expect(count).toBeGreaterThanOrEqual(2);

  const rules = await scripts.evaluateAll((nodes) =>
    nodes.map((node) => JSON.parse(node.textContent ?? "{}")),
  );

  const selectors = rules.map(
    (rule) => rule.prerender?.[0]?.where?.selector_matches as string,
  );
  expect(selectors).toEqual(
    expect.arrayContaining([
      "a.rankings-pagination__link",
      "a.catalogue-pagination__link",
    ]),
  );

  // Every declared selector must actually match anchors on the page, otherwise
  // the rule is inert.
  for (const selector of selectors) {
    expect(
      await page.locator(selector).count(),
      `speculation rule selector ${selector} matches nothing`,
    ).toBeGreaterThan(0);
  }

  // The `rel="prefetch"` fallback for engines without speculation support.
  const prefetchLinks = page.locator(
    "[data-rankings-next], [data-rankings-prev]",
  );
  const prefetchCount = await prefetchLinks.count();
  expect(prefetchCount).toBeGreaterThan(0);
  for (let i = 0; i < prefetchCount; i += 1) {
    await expect(prefetchLinks.nth(i)).toHaveAttribute("rel", "prefetch");
  }

  const catalogueLinks = page.locator("a.catalogue-pagination__link");
  const catalogueCount = await catalogueLinks.count();
  expect(catalogueCount).toBeGreaterThan(0);
  for (let i = 0; i < catalogueCount; i += 1) {
    await expect(catalogueLinks.nth(i)).toHaveAttribute("rel", "prefetch");
  }
});

test("legal pages share the /about content gutter", async ({ page }) => {
  const leftEdge = async (path: string): Promise<number> => {
    await page.goto(path);
    const box = await page.locator("h1").first().boundingBox();
    expect(box, `no h1 on ${path}`).not.toBeNull();
    return box!.x;
  };

  const about = await leftEdge("/about");
  const privacy = await leftEdge("/privacy-policy");
  const terms = await leftEdge("/terms-of-use");

  // No extra padding container, so all three start at the same gutter.
  expect(Math.abs(privacy - about)).toBeLessThanOrEqual(1);
  expect(Math.abs(terms - about)).toBeLessThanOrEqual(1);
});
