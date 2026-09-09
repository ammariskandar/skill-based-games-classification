import { expect, test, type Page } from "@playwright/test";

/**
 * SBGC-222: profile editing modal.
 *
 * Exercises the real `EditProfileModal` on the `/dev/edit-profile` fixture (no
 * Django backend). The profile-update fetch is mocked with `page.route` so the
 * save flow can be verified end-to-end without a running backend.
 */

async function openModal(page: Page): Promise<void> {
  await page.goto("/dev/edit-profile");
  await page.locator("#edit-profile-btn").waitFor();
  await page.click("#edit-profile-btn");
}

test("edit button opens the dialog and traps focus", async ({ page }) => {
  await openModal(page);
  await expect(page.locator("#edit-profile-modal")).toBeVisible();

  const focusedInDialog = await page.evaluate(() => {
    const dialog = document.getElementById("edit-profile-modal");
    return dialog !== null && dialog.contains(document.activeElement);
  });
  expect(focusedInDialog).toBe(true);
});

test("avatar and solid border update the live preview with a 12px shadow", async ({
  page,
}) => {
  await openModal(page);

  await page.check('input[name="pf-avatar"][value="anime_male_2"]', {
    force: true,
  });
  await expect(page.locator("#modal-avatar-img")).toHaveAttribute(
    "src",
    "/assets/avatars/anime_male_2.avif",
  );

  await page.check('input[name="pf-border-type"][value="SOLID"]');
  await page.fill("#pf-border-color-hex", "#00FFCC");

  const shadow = await page
    .locator("#modal-avatar-ring")
    .evaluate((el) => (el as HTMLElement).style.boxShadow);
  expect(shadow.toLowerCase()).toContain("12px");
  // Chromium serializes the hex color back as its rgb() equivalent.
  expect(shadow.toLowerCase()).toContain("rgb(0, 255, 204)");
});

test("saving bbcode updates the bio card without a full reload", async ({
  page,
}) => {
  await page.route("**/api/profile/update", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        username: "fixture-user",
        first_name: "Fixture",
        last_name: "User",
        bio: "[b]Hello[/b] [img]https://example.com/badge.png[/img]",
        bio_mode: "BBCODE",
        avatar_key: "male_1",
        border_type: "NONE",
        border_preset_id: null,
        border_color: "",
      }),
    });
  });

  await openModal(page);

  // Switch to BBCode mode and enter a badge embed.
  await page.click('button[data-bio-tab="BBCODE"]');
  await page.fill(
    "#pf-bio-bbcode",
    "[b]Hello[/b] [img]https://example.com/badge.png[/img]",
  );

  await page.click("#edit-profile-save");

  await expect(page.locator("#edit-profile-modal")).not.toBeVisible();

  // A single image embed renders at full size (no micro-badge constraint).
  const image = page.locator("#profile-bio-card img");
  await expect(image).toHaveCount(1);
  await expect(image).toHaveAttribute("class", /max-w-full/);
  await expect(image).not.toHaveAttribute("class", /max-h-12/);
  await expect(page.locator("#profile-bio-card")).toContainText("Hello");
  // Still on the fixture route — no navigation/reload occurred.
  expect(new URL(page.url()).pathname).toBe("/dev/edit-profile");
});
