import { expect, test } from "@playwright/test";

/**
 * SBGC-240: legal pages, their permanent redirect aliases, and their footer
 * entry points.
 *
 * `page.goto` follows redirects, so the 301 aliases are observed through the
 * `request` fixture with `maxRedirects: 0` to inspect the raw status and
 * `Location` header.
 */

test.describe("legal pages", () => {
  test("/privacy-policy renders the policy with status 200", async ({
    page,
  }) => {
    const response = await page.goto("/privacy-policy");
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { level: 1, name: /privacy policy/i }),
    ).toBeVisible();
  });

  test("/terms-of-use renders the terms with status 200", async ({ page }) => {
    const response = await page.goto("/terms-of-use");
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole("heading", { level: 1, name: /terms of use/i }),
    ).toBeVisible();
  });

  test("/privacy permanently redirects to /privacy-policy", async ({
    request,
  }) => {
    const response = await request.get("/privacy", { maxRedirects: 0 });
    expect(response.status()).toBe(301);
    expect(response.headers()["location"]).toBe("/privacy-policy");
  });

  test("/terms permanently redirects to /terms-of-use", async ({ request }) => {
    const response = await request.get("/terms", { maxRedirects: 0 });
    expect(response.status()).toBe(301);
    expect(response.headers()["location"]).toBe("/terms-of-use");
  });
});

test("the footer links to the legal pages and shows the new tagline", async ({
  page,
}) => {
  await page.goto("/");

  const footer = page.locator("footer");

  await expect(
    footer.getByRole("link", { name: "Privacy Policy", exact: true }),
  ).toHaveAttribute("href", "/privacy-policy");
  await expect(
    footer.getByRole("link", { name: "Terms of Use", exact: true }),
  ).toHaveAttribute("href", "/terms-of-use");
  await expect(
    footer.getByRole("link", { name: "About", exact: true }),
  ).toHaveAttribute("href", "/about");
  await expect(
    footer.getByRole("link", { name: "Methodology", exact: true }),
  ).toHaveAttribute("href", "/methodology");

  await expect(
    footer.getByText(/A revolutionary way to categorize games better\./),
  ).toBeVisible();
});
