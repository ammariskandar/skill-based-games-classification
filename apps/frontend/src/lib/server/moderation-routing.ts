/**
 * Moderation lockout routing — SBGC-223.
 *
 * Pure decision helper for the SSR middleware: given the viewer's lockout
 * status and the page they are trying to reach, return the remediation target
 * to redirect to, or `null` to let the request through.  Kept free of Astro
 * imports so it is unit-testable.
 *
 * Asymmetry is intentional (matches the backend perimeter):
 *
 * - `pending_username_change` may only reach the forced-username form (plus a
 *   small auth allow-list so the user can log out).
 * - `pending_bio_change` may reach their own profile, where the unclosable
 *   Edit Profile modal performs the remediation.
 */

export const LOCKOUT_PENDING_USERNAME = "pending_username_change";
export const LOCKOUT_PENDING_BIO = "pending_bio_change";

export const USERNAME_REMEDIATION_PATH = "/remediate/username";

/** Auth surfaces a locked-out user must retain to recover or log out. */
const AUTH_ALLOW_LIST = [
  "/login",
  "/logout",
  "/signup",
  "/verify-email",
  "/signup-error",
  "/reset",
  "/reset-password",
];

export interface ModerationRedirectInput {
  pathname: string;
  status: string | null;
  username: string | null;
}

function isAuthPath(pathname: string): boolean {
  return AUTH_ALLOW_LIST.some(
    (path) => pathname === path || pathname.startsWith(`${path}/`),
  );
}

/** Return the redirect target for a lockout, or `null` to continue. */
export function moderationRedirect({
  pathname,
  status,
  username,
}: ModerationRedirectInput): string | null {
  if (!status || isAuthPath(pathname)) return null;

  if (status === LOCKOUT_PENDING_USERNAME) {
    const alreadyThere = pathname === USERNAME_REMEDIATION_PATH;
    return alreadyThere ? null : USERNAME_REMEDIATION_PATH;
  }

  if (status === LOCKOUT_PENDING_BIO) {
    if (!username) return null;
    const profilePath = `/profile/${username}`;
    return pathname === profilePath ? null : profilePath;
  }

  return null;
}

/** True for a navigational page request (not an asset or BFF endpoint). */
export function isPageRequest(pathname: string): boolean {
  if (pathname.startsWith("/api/") || pathname.startsWith("/_")) return false;
  if (pathname === "/favicon.ico") return false;
  // Any path with a file extension is a static asset, not a page.
  return !/\.[a-z0-9]+$/i.test(pathname);
}
