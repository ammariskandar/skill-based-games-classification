import { expect, test, type Page } from "@playwright/test";

/**
 * SBGC-223: user reporting + forced remediation.
 *
 * Exercises the real `ReportUserModal` and `EditProfileModal` on the
 * `/dev/report-user` and `/dev/profile-bio-lockout` fixtures (no Django
 * backend). The BFF boundaries are mocked:
 *
 *   GET  /api/auth/status                → auth gate
 *   POST /api/reports/user               → report ingestion outcome
 *   POST /api/profile/update             → forced bio remediation outcome
 */

const AUTH_URL = "**/api/auth/status";
const REPORT_URL = "**/api/reports/user";
const PROFILE_URL = "**/api/profile/update";

async function mockAuth(page: Page, authenticated = true): Promise<void> {
  await page.route(AUTH_URL, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated,
        username: authenticated ? "reporter" : null,
      }),
    }),
  );
}

async function mockReport(
  page: Page,
  body: unknown,
  status = 200,
): Promise<void> {
  await page.route(REPORT_URL, (route) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    }),
  );
}

async function openReportModal(page: Page): Promise<void> {
  await mockAuth(page);
  await page.goto("/dev/report-user");
  await page.click("#report-user-btn");
  await expect(page.locator("#report-user-modal")).toBeVisible();
}

test("self profile shows Edit Profile and hides Report User", async ({
  page,
}) => {
  await page.goto("/dev/report-user?viewer=owner");
  await expect(page.locator("#edit-profile-btn")).toBeVisible();
  await expect(page.locator("#report-user-btn")).toHaveCount(0);
});

test("another profile shows the Report User button", async ({ page }) => {
  await page.goto("/dev/report-user");
  await expect(page.locator("#report-user-btn")).toBeVisible();
  await expect(page.locator("#edit-profile-btn")).toHaveCount(0);
});

test("unauthenticated click shows an inline login toast, not the dialog", async ({
  page,
}) => {
  await mockAuth(page, false);
  await page.goto("/dev/report-user");
  await page.click("#report-user-btn");

  await expect(page.locator("#report-user-toast")).toBeVisible();
  await expect(page.locator("#report-user-toast a")).toHaveAttribute(
    "href",
    /\/login\?redirect=/,
  );
  await expect(page.locator("#report-user-modal")).not.toBeVisible();
});

test("submit stays disabled until at least one reason is checked", async ({
  page,
}) => {
  await openReportModal(page);
  const submit = page.locator("[data-report-submit]");
  await expect(submit).toBeDisabled();

  await page.check('[data-report-reason="reason_username"]');
  await expect(submit).toBeEnabled();

  await page.uncheck('[data-report-reason="reason_username"]');
  await expect(submit).toBeDisabled();
});

test("Other checkbox unlocks the textarea and unchecking clears it", async ({
  page,
}) => {
  await openReportModal(page);
  const other = page.locator("[data-report-other]");
  await expect(other).toBeDisabled();

  await page.check('[data-report-reason="reason_other"]');
  await expect(other).toBeEnabled();
  await other.fill("Some detail");
  await expect(other).toHaveValue("Some detail");

  await page.uncheck('[data-report-reason="reason_other"]');
  await expect(other).toBeDisabled();
  await expect(other).toHaveValue("");
});

test("the Other field is capped at 250 characters and strips angle brackets", async ({
  page,
}) => {
  await openReportModal(page);
  await page.check('[data-report-reason="reason_other"]');
  const other = page.locator("[data-report-other]");
  await expect(other).toHaveAttribute("maxlength", "250");

  await other.pressSequentially("x".repeat(260));
  const length = await other.evaluate(
    (el) => (el as HTMLTextAreaElement).value.length,
  );
  expect(length).toBe(250);

  await other.fill("");
  await other.pressSequentially("a<b>c");
  await expect(other).toHaveValue("abc");
});

test("a successful report shows the confirmation view", async ({ page }) => {
  await mockReport(page, {
    success: true,
    message: "Report submitted successfully.",
  });
  await openReportModal(page);

  await page.check('[data-report-reason="reason_bio"]');
  await page.click("[data-report-submit]");

  await expect(page.locator("[data-report-success]")).toBeVisible();
  await expect(page.locator("[data-report-form]")).toBeHidden();
});

test("a rejected report keeps the selection and shows an error", async ({
  page,
}) => {
  await mockReport(
    page,
    {
      error: {
        code: "VALIDATION_ERROR",
        message: "You cannot report yourself.",
      },
    },
    422,
  );
  await openReportModal(page);

  const reason = page.locator('[data-report-reason="reason_username"]');
  await reason.check();
  await page.click("[data-report-submit]");

  await expect(page.locator("[data-report-error]")).toContainText(
    "You cannot report yourself.",
  );
  await expect(reason).toBeChecked();
});

test("a forced bio lockout opens an unclosable modal until a real edit is made", async ({
  page,
}) => {
  await page.route(PROFILE_URL, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        username: "locked-user",
        first_name: "Changed",
        last_name: "User",
        bio: "Existing bio",
        bio_mode: "PLAIN",
        avatar_key: "male_1",
        border_type: "NONE",
        border_preset_id: null,
        border_color: "",
      }),
    }),
  );

  await page.goto("/dev/profile-bio-lockout");

  const dialog = page.locator("#edit-profile-modal");
  await expect(dialog).toBeVisible();
  await expect(page.locator("#profile-lockout-banner")).toBeVisible();

  // Close controls are removed from the DOM and Save is gated on a real delta.
  await expect(page.locator("#edit-profile-close")).toHaveCount(0);
  await expect(page.locator("#edit-profile-cancel")).toHaveCount(0);
  const save = page.locator("#edit-profile-save");
  await expect(save).toBeDisabled();

  // Escape must not dismiss it.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeVisible();

  await page.fill("#pf-first-name", "Changed");
  await expect(save).toBeEnabled();

  await page.click("#edit-profile-save");

  await expect(dialog).not.toBeVisible();
  await expect(page.locator("#profile-lockout-banner")).toHaveCount(0);
});
