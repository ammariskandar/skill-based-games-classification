/**
 * User-profile API boundary — SBGC-221.
 *
 * Server-side only: fetches the SBGC-221 public profile DTO from Django.
 * Distinguishes a user-not-found (Django 404) from backend/service failures so
 * the route can render a real 404 versus a real error page.
 */

import { getJSON } from "./client";
import { BackendApiError } from "./games";
import type { PublicUserProfileDto } from "../../../types/api";

export type {
  ProfileScoresDto,
  PublicUserProfileDto,
  TopGameDto,
} from "../../../types/api";

/** The username does not resolve to a registered user (Django 404). */
export class UserNotFoundError extends Error {
  constructor(readonly username: string) {
    super(`User not found: ${username}`);
    this.name = "UserNotFoundError";
  }
}

/** Optional per-call adapter inputs. */
export interface UserProfileOptions {
  /** Viewer `sessionid` cookie value, forwarded so Django can flag ownership. */
  sessionId?: string;
  signal?: AbortSignal;
}

/** Fetch one public user profile from Django (SBGC-221). */
export async function getUserProfile(
  username: string,
  options: UserProfileOptions = {},
): Promise<PublicUserProfileDto> {
  const headers: Record<string, string> = {};
  if (options.sessionId) {
    headers.Cookie = `sessionid=${options.sessionId}`;
  }

  const result = await getJSON<PublicUserProfileDto>(
    `/api/v1/users/${encodeURIComponent(username)}`,
    {
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      signal: options.signal,
    },
  );

  if (result.ok) {
    if ("data" in result) return result.data;
    throw new BackendApiError("Unexpected empty response from the API.");
  }
  if (result.status === 404) {
    throw new UserNotFoundError(username);
  }
  throw new BackendApiError(result.error.message, result);
}
