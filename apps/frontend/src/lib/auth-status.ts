/**
 * Client-side auth-status cache — SBGC-217 follow-up.
 *
 * The navbar auth island and the login page share a small `sessionStorage`
 * cache so a known username paints instantly on the next navigation instead
 * of waiting for the `/api/auth/status` round-trip on every page load (which
 * made the navbar auth controls shift while the fetch was in flight).
 *
 * The BFF status endpoint remains the source of truth: each page refresh
 * re-validates in the background and overwrites the cache.  A logout
 * (`flash_toast=logout_success`) or a fresh login clears/rewrites the cache.
 */

export interface AuthStatus {
  authenticated: boolean;
  username: string | null;
}

export const AUTH_STATUS_CACHE_KEY = "mygamedna:auth-status:v1";

export function readCachedAuthStatus(): AuthStatus | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STATUS_CACHE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const candidate = parsed as Partial<AuthStatus>;
    if (typeof candidate.authenticated !== "boolean") return null;
    return {
      authenticated: candidate.authenticated,
      username:
        typeof candidate.username === "string" ? candidate.username : null,
    };
  } catch {
    // Storage unavailable or unparseable — the status fetch still works.
    return null;
  }
}

export function writeCachedAuthStatus(status: AuthStatus): void {
  try {
    sessionStorage.setItem(AUTH_STATUS_CACHE_KEY, JSON.stringify(status));
  } catch {
    // Storage unavailable (private mode/quota) — the status fetch still works.
  }
}

export function clearCachedAuthStatus(): void {
  try {
    sessionStorage.removeItem(AUTH_STATUS_CACHE_KEY);
  } catch {
    // Nothing to clear.
  }
}
