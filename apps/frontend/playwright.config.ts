import { defineConfig, devices } from "@playwright/test";

/**
 * Targeted real-browser interaction tests (SBGC-192).
 *
 * This suite exists for F2/F3 frontend work — features whose correctness
 * depends on real browser scrolling, animation, gesture, geometry, or timing.
 * It is intentionally separate from the Vitest unit suite and is not part of
 * the default `npm test` flow; run it explicitly via `test:frontend:browser`.
 */
export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:4321",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --port 4321",
    port: 4321,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
