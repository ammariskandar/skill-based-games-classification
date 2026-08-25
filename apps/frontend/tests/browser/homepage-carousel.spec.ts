import { expect, test, type Page } from "@playwright/test";

/**
 * Real-browser regression for the SBGC-189/191 homepage carousel (SBGC-192) plus
 * the SBGC-193 simplified lighting contract.
 *
 * This suite proves, in a real Chromium runtime with real smooth-scroll timing,
 * that the carousel loops indefinitely in both directions without reaching a
 * permanent physical boundary, and that the default/hover brightness contract
 * (65% default, 100% hover/focus) holds. It asserts computed styles, not pixels,
 * so it avoids fragile screenshot comparisons.
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

test("cards are uniformly dimmed and hover reveals full brightness", async ({
  page,
}) => {
  await open(page);

  // Every visible canonical card renders at brightness(0.65).
  const defaultBrightness = await page.evaluate(() => {
    const track = document.querySelector<HTMLElement>("[data-carousel-track]")!;
    const trackRect = track.getBoundingClientRect();
    return Array.from(
      track.querySelectorAll<HTMLElement>(
        "[data-carousel-card]:not([data-carousel-clone])",
      ),
    )
      .filter((card) => {
        const r = card.getBoundingClientRect();
        return r.right > trackRect.left && r.left < trackRect.right;
      })
      .map((card) => {
        const img = card.querySelector<HTMLImageElement>("img")!;
        const m = /brightness\(([^)]+)\)/.exec(getComputedStyle(img).filter);
        return m ? Number.parseFloat(m[1]) : Number.NaN;
      });
  });

  expect(defaultBrightness.length).toBeGreaterThan(0);
  for (const b of defaultBrightness) expect(b).toBeCloseTo(0.65, 2);

  // Hover a clearly-visible middle card (not the flush card at the left edge),
  // so Playwright's scroll-into-view does not nudge the carousel and trigger the
  // loop normalization mid-test.
  const card = page
    .locator("[data-carousel-card]:not([data-carousel-clone])")
    .nth(2);

  const brightness = () =>
    card.evaluate((el) => {
      const img = el.querySelector<HTMLImageElement>("img")!;
      const m = /brightness\(([^)]+)\)/.exec(getComputedStyle(img).filter);
      return m ? Number.parseFloat(m[1]) : Number.NaN;
    });

  const transform = () => card.evaluate((el) => getComputedStyle(el).transform);

  // Hover: full brightness + slight enlargement (poll until both transitions
  // fully settle, rather than using a fixed delay that can race under load).
  await card.hover();
  await expect.poll(brightness, { timeout: 3000 }).toBeCloseTo(1, 2);
  await expect.poll(transform, { timeout: 3000 }).toContain("1.02");

  // Unhover: returns to default dimmed brightness.
  await page.mouse.move(0, 0);
  await expect.poll(brightness, { timeout: 3000 }).toBeCloseTo(0.65, 2);
});

test("cards use intrinsic rem sizing so browser zoom scales them", async ({
  page,
}) => {
  const cardWidth = () =>
    page.evaluate(() => {
      const card = document.querySelector<HTMLElement>(
        "[data-carousel-card]:not([data-carousel-clone])",
      );
      return card ? card.getBoundingClientRect().width : null;
    });

  await page.setViewportSize({ width: 1280, height: 800 });
  await open(page);
  const widthAt1280 = await cardWidth();

  // 1024px CSS viewport ≈ 125% browser zoom on a 1280px display.
  await page.setViewportSize({ width: 1024, height: 800 });
  await waitForSettle(page);
  const widthAt1024 = await cardWidth();

  expect(widthAt1280).not.toBeNull();
  expect(widthAt1024).not.toBeNull();
  // A fixed `rem` basis keeps the rendered CSS width constant across viewport
  // widths, which is what makes browser zoom scale the card physically. A
  // viewport-fraction basis (the old calc((100% - …)/N)) would shrink here.
  expect(widthAt1024!).toBeCloseTo(widthAt1280!, 0);
  // Desktop tier ≈ 15rem = 240px at the default 16px root.
  expect(widthAt1024!).toBeGreaterThan(225);
  expect(widthAt1024!).toBeLessThan(255);
});

test("loops forward across multiple wraps at a wide viewport", async ({
  page,
}) => {
  // A wide viewport shows more than the fixed 5-card desktop tier, which used
  // to leave the clone buffer too small and stall forward looping at the
  // physical end of the track.
  await page.setViewportSize({ width: 1920, height: 800 });
  await open(page);
  expect(await flushName(page)).toBe(name(1));

  for (let k = 1; k <= 12; k++) {
    await page.click("[data-carousel-next]");
    await waitForSettle(page);
    expect(await flushName(page)).toBe(name((k % GAME_COUNT) + 1));
  }
});
