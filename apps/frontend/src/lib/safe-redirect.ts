/**
 * Same-origin return-path guard — SBGC-241.
 *
 * `?redirect=` is attacker-controllable, so a post-login navigation must only
 * ever accept an absolute path on this origin. Anything protocol-relative
 * (`//evil.test`), absolute (`https://evil.test`), scheme-bearing
 * (`javascript:…`), or containing a backslash (some engines normalise `\` to
 * `/`, which would re-open the hole) falls back to the default destination.
 *
 * Shared by the login page's server-side bounce and its client-side success
 * navigation so the two cannot drift apart.
 */
export function safeRedirectTarget(
  candidate: string | null | undefined,
  fallback = "/",
): string {
  if (typeof candidate !== "string") return fallback;
  const trimmed = candidate.trim();
  if (!trimmed.startsWith("/")) return fallback;
  if (trimmed.startsWith("//")) return fallback;
  if (trimmed.includes("\\")) return fallback;
  return trimmed;
}
