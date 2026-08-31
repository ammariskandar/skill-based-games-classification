import { expect, test } from "@playwright/test";

/**
 * SBGC-101: standardized error pages.
 *
 * The custom 404 page must be served with a real 404 status and render the
 * recovery actions (Browse Catalogue / Go Home) without leaking any raw
 * backend payloads.
 */

test("custom 404 page serves status 404 with recovery links", async ({
  page,
}) => {
  const response = await page.goto("/this-route-does-not-exist");
  expect(response?.status()).toBe(404);

  await expect(
    page.getByRole("heading", { name: /page not found/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /browse catalogue/i }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /go home/i })).toBeVisible();
});
