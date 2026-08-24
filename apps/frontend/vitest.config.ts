import { getViteConfig } from "astro/config";

const base = getViteConfig({});

export default {
  ...base,
  test: {
    environment: "node",
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
    // Vitest is for unit/helper tests co-located under `src/`. The real-browser
    // Playwright suite lives in `tests/browser/` and must not be picked up here.
    include: ["src/**/*.{test,spec}.?(c|m)[jt]s?(x)"],
  },
};
