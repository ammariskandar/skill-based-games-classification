import { expect, test, type Page } from "@playwright/test";

/**
 * Real-browser regression for the SBGC-189/191 homepage carousel (SBGC-192).
 *
 * This suite proves, in a real Chromium runtime with real smooth-scroll timing,
 * that the carousel loops indefinitely in both directions without reaching a
 * permanent physical boundary. It intentionally does not assert brightness or
 * other perceptual properties — those remain human-validated.
 *
 * The fixture page (`/dev/carousel`) renders the real `HomepageCarousel`
 * component with 10 static games, so no Django backend or Steam network access
 * is required.
 */

const GAME_COUNT = 10;
const name = (i: number) => `Fixture Game ${i}`;

/** Title of the card whose left edge is nearest the snap origin. */
function flushName(page: Page): Promise<string | null> {
  return page.evaluate(() => {
    const track = document.querySelector<HTMLElement>("[data-carousel-track]");
    if (!track) return null;
    const cards = Array.from(
      track.querySelectorAll<HTMLElement>("[data-carousel-card]"),
    );
    let best: HTMLElement | null = null;
    let bestDist = Number.POSITIVE_INFINITY;
    for (const card of cards) {
      const dist = Math.abs(card.getBoundingClientRect().left);
      if (dist < bestDist) {
        bestDist = dist;
        best = card;
      }
    }
    return (
      best?.querySelector(".homepage-carousel__title")?.textContent?.trim() ??
      null
    );
  });
}

function scrollLeft(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      document.querySelector<HTMLElement>("[data-carousel-track]")
        ?.scrollLeft ?? -1,
  );
}

/**
 * Wait until the track's scroll offset has been stable for 200ms. The
 * component normalizes loop position via a 120ms debounce after the last scroll
 * event, so 200ms of stability guarantees that normalization has also run.
 */
function waitForSettle(page: Page): Promise<unknown> {
  return page.waitForFunction(
    () =>
      new Promise<boolean>((resolve) => {
        const track = document.querySelector<HTMLElement>(
          "[data-carousel-track]",
        );
        if (!track) {
          resolve(true);
          return;
        }
        let last = track.scrollLeft;
        let lastChange = performance.now();
        const id = setInterval(() => {
          const now = track.scrollLeft;
          const t = performance.now();
          if (Math.abs(now - last) >= 0.5) {
            last = now;
            lastChange = t;
          }
          if (t - lastChange >= 200) {
            clearInterval(id);
            resolve(true);
          }
        }, 20);
      }),
    undefined,
    { timeout: 5000 },
  );
}

async function open(page: Page): Promise<void> {
  await page.goto("/dev/carousel");
  await page.locator("[data-carousel-track]").waitFor();
  await waitForSettle(page);
}

test("harness proof: smooth scroll produces intermediate motion", async ({
  page,
}) => {
  await open(page);

  const positions = await page.evaluate(
    () =>
      new Promise<number[]>((resolve) => {
        const track = document.querySelector<HTMLElement>(
          "[data-carousel-track]",
        )!;
        const next = document.querySelector<HTMLButtonElement>(
          "[data-carousel-next]",
        )!;
        const seen: number[] = [];
        const onScroll = () => seen.push(Math.round(track.scrollLeft));
        track.addEventListener("scroll", onScroll, { passive: true });
        next.click();
        setTimeout(() => {
          track.removeEventListener("scroll", onScroll);
          resolve(seen);
        }, 800);
      }),
  );

  // A real smooth scroll must pass through more than one distinct position.
  // An instant-only harness (e.g. virtual-time headless) would collapse this.
  expect(positions.length).toBeGreaterThan(2);
});

test("loops forward across multiple wraps", async ({ page }) => {
  await open(page);
  expect(await flushName(page)).toBe(name(1));

  // 22 clicks = two full wraps plus two extra steps.
  for (let k = 1; k <= 22; k++) {
    await page.click("[data-carousel-next]");
    await waitForSettle(page);
    const expected = (k % GAME_COUNT) + 1;
    expect(await flushName(page)).toBe(name(expected));
  }
});

test("loops backward across multiple wraps (no left boundary lock)", async ({
  page,
}) => {
  await open(page);
  expect(await flushName(page)).toBe(name(1));

  // This is the historical SBGC-191 regression: Previous used to hit a real
  // physical left boundary. 22 clicks = two full wraps plus two extra steps.
  for (let k = 1; k <= 22; k++) {
    await page.click("[data-carousel-prev]");
    await waitForSettle(page);
    const expected = ((GAME_COUNT - (k % GAME_COUNT)) % GAME_COUNT) + 1;
    expect(await flushName(page)).toBe(name(expected));
  }

  // The track must not be pinned at the physical start.
  expect(await scrollLeft(page)).toBeGreaterThan(1);
});

test("reduced-motion still loops (instant path)", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page);

  const positions: number[] = [];
  for (let i = 0; i < 12; i++) {
    await page.click("[data-carousel-prev]");
    await waitForSettle(page);
    positions.push(await scrollLeft(page));
  }

  // Instant path must still move and must not get stuck at a single offset.
  const distinct = new Set(positions);
  expect(distinct.size).toBeGreaterThan(5);
});

test("loops at a smaller supported viewport", async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 800 });
  await open(page);
  expect(await flushName(page)).toBe(name(1));

  for (let k = 1; k <= 11; k++) {
    await page.click("[data-carousel-next]");
    await waitForSettle(page);
    expect(await flushName(page)).toBe(name((k % GAME_COUNT) + 1));
  }
});
