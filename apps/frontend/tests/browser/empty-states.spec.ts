import { expect, test } from "@playwright/test";

/**
 * SBGC-241 (Req 5A/5B/6): actionable dead ends.
 *
 * - Header search offers a suggestion CTA when a non-empty query matches nothing.
 * - The catalogue search empty state leads with the suggestion CTA.
 * - The footer tagline is the single rolled-back sentence.
 */

const SUGGEST_HREF = /\/about\?action=suggest$/;
const TAGLINE = "A revolutionary way to categorize games better.";

test.describe("header search empty state", () => {
  test("a non-empty query with no matches offers a suggestion CTA", async ({
    page,
  }) => {
    // Stub the search index with an empty list so the "no matches" path is
    // deterministic and needs no Django backend.
    await page.route("**/api/search-index", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ games: [] }),
      }),
    );

    await page.goto("/dev/navbar");

    const search = page.locator('[data-header-search="desktop"]');
    await search.locator(".header-search__toggle").click();

    const input = search.locator(".header-search__input");
    await expect(input).toBeVisible();
    // No query yet: the dropdown stays collapsed (no CTA on bare focus).
    await expect(search.locator(".header-search__suggestions")).toBeHidden();
    await expect(search.locator("#search-option-suggest")).toHaveCount(0);

    await input.fill("zzzz-no-such-game");

    const cta = search.locator("#search-option-suggest");
    await expect(cta).toBeVisible();
    await expect(cta).toHaveAttribute("role", "option");
    await expect(cta).toHaveAttribute("aria-selected", "false");
    await expect(cta).toContainText(
      "Can't find your game? Submit a suggestion",
    );
    await expect(cta.locator("a")).toHaveAttribute("href", SUGGEST_HREF);
  });

  test("an empty query keeps the dropdown hidden", async ({ page }) => {
    await page.route("**/api/search-index", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ games: [] }),
      }),
    );

    await page.goto("/dev/navbar");

    const search = page.locator('[data-header-search="desktop"]');
    await search.locator(".header-search__toggle").click();

    const input = search.locator(".header-search__input");
    await input.fill("   ");

    await expect(search.locator(".header-search__suggestions")).toBeHidden();
    await expect(search.locator("#search-option-suggest")).toHaveCount(0);
  });
});

test("the catalogue search empty state leads with the suggestion CTA", async ({
  page,
}) => {
  await page.goto("/catalogue?q=zzzznonexistentgamezzzz");

  const suggest = page.getByRole("link", {
    name: "Submit a game suggestion",
  });
  const viewCatalogue = page.getByRole("link", {
    name: "View full catalogue",
  });

  await expect(suggest).toBeVisible();
  await expect(suggest).toHaveAttribute("href", "/about?action=suggest");
  await expect(viewCatalogue).toBeVisible();

  // The CTA must precede "View full catalogue" in document order.
  const order = await page.evaluate(() => {
    const links = Array.from(document.querySelectorAll("a"));
    const byText = (label: string) =>
      links.find((link) => (link.textContent ?? "").trim() === label);
    const suggestion = byText("Submit a game suggestion");
    const catalogue = byText("View full catalogue");
    if (!suggestion || !catalogue) return "missing";
    return suggestion.compareDocumentPosition(catalogue) &
      Node.DOCUMENT_POSITION_FOLLOWING
      ? "before"
      : "after";
  });
  expect(order).toBe("before");
});

test("the footer renders only the single-sentence tagline", async ({
  page,
}) => {
  await page.goto("/");

  const footer = page.locator("footer");
  const tagline = footer.locator("p.mt-1");

  await expect(tagline).toHaveText(TAGLINE);
  // The previous longer sentence is gone.
  await expect(footer).not.toContainText(
    "Classifying games through the lens of skill",
  );
});
