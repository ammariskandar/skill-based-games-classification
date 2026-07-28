import { getViteConfig } from "astro/config";

const base = getViteConfig({});

export default {
  ...base,
  test: {
    environment: "node",
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
  },
};
