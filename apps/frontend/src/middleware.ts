/**
 * Global SSR middleware — SBGC-109.
 *
 * Strips server-identification banner headers (`Server`, `X-Powered-By`) from
 * every server-rendered response so the Astro runtime never advertises its
 * framework, Node runtime, or an underlying Express-style server.  The rule
 * lives in `lib/server/banner-headers.ts` so it is unit-testable without the
 * Astro virtual module.
 */
import { defineMiddleware } from "astro:middleware";

import { stripServerIdentificationHeaders } from "./lib/server/banner-headers";

export const onRequest = defineMiddleware(async (_context, next) => {
  const response = await next();
  if (response) {
    stripServerIdentificationHeaders(response.headers);
  }
  return response;
});
