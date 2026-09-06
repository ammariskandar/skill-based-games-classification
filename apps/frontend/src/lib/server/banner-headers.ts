/**
 * SSR banner-header hygiene — SBGC-109.
 *
 * Server-identification headers (`Server`, `X-Powered-By`) advertise the
 * runtime and version to attackers and must never be emitted by the Astro SSR
 * runtime (or an underlying Node/Express-style runtime).  The pure helper is
 * kept out of `astro:middleware` so Vitest can exercise it directly; the
 * `src/middleware.ts` `onRequest` hook applies it to every SSR response.
 */

/** Header names stripped from every outgoing SSR response (case-insensitive). */
export const FORBIDDEN_BANNER_HEADERS = new Set(["server", "x-powered-by"]);

/** Remove server-identification headers in place from an outgoing response. */
export function stripServerIdentificationHeaders(headers: Headers): void {
  for (const name of FORBIDDEN_BANNER_HEADERS) {
    headers.delete(name);
  }
}
