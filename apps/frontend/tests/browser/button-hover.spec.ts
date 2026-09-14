import { expect, test, type Locator } from "@playwright/test";

/**
 * SBGC-241: saturated buttons must brighten on hover, never darken.
 *
 * The old `hover:opacity-90` composited the fill toward the dark page
 * background. These tests assert the computed background colour actually gets
 * brighter (relative luminance rises by a noticeable margin) and that the
 * resting colour is still the design-system blue, so the assertion fails if a
 * button silently stops being a saturated blue button.
 */

const REST_BLUE = "rgb(88, 166, 255)"; // --color-blue #58a6ff
const HOVER_BLUE = "rgb(121, 192, 255)"; // --color-blue-hover #79c0ff
const MIN_LUMINANCE_GAIN = 1.08; // hover luminance must be >= 8% higher

function relativeLuminance(rgb: string): number {
  const channels = rgb
    .match(/[\d.]+/g)
    ?.slice(0, 3)
    .map(Number);
  if (!channels || channels.length !== 3) {
    throw new Error(`Unparseable colour: ${rgb}`);
  }
  const linearize = (channel: number) => {
    const c = channel / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const [r, g, b] = channels.map(linearize);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

async function backgroundColor(locator: Locator): Promise<string> {
  return locator.evaluate((el) => getComputedStyle(el).backgroundColor);
}

/**
 * Asserts the element rests on the saturated blue, hovers it, waits for the
 * colour transition to settle, and returns [restLuminance, hoverLuminance].
 */
async function measureHoverBrightening(
  locator: Locator,
): Promise<[number, number]> {
  const rest = await backgroundColor(locator);
  expect(rest).toBe(REST_BLUE);
  const restLuminance = relativeLuminance(rest);

  await locator.hover();
  await expect.poll(async () => backgroundColor(locator)).toBe(HOVER_BLUE);

  const hovered = await backgroundColor(locator);
  const hoverLuminance = relativeLuminance(hovered);
  expect(hoverLuminance).toBeGreaterThan(restLuminance * MIN_LUMINANCE_GAIN);
  return [restLuminance, hoverLuminance];
}

test("the Log In button brightens on hover", async ({ page }) => {
  await page.goto("/login");
  const [rest, hover] = await measureHoverBrightening(
    page.locator("#login-submit"),
  );
  expect(hover).toBeGreaterThan(rest * MIN_LUMINANCE_GAIN);
});

test("the Find Username button on /reset brightens on hover", async ({
  page,
}) => {
  await page.goto("/reset");
  const [rest, hover] = await measureHoverBrightening(
    page.locator("#forgot-username-submit"),
  );
  expect(hover).toBeGreaterThan(rest * MIN_LUMINANCE_GAIN);
});

test("the Send Reset Link button on /reset brightens on hover", async ({
  page,
}) => {
  await page.goto("/reset");
  await page.locator("#tab-password").click();
  const [rest, hover] = await measureHoverBrightening(
    page.locator("#forgot-password-submit"),
  );
  expect(hover).toBeGreaterThan(rest * MIN_LUMINANCE_GAIN);
});
