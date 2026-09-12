/**
 * Moderation / security API boundary — SBGC-223.
 *
 * Server-side only (Astro API routes and middleware).  Uses raw `fetch` rather
 * than the shared `client.ts` transport because the report BFF must relay the
 * exact upstream status (200 filed or merged / 4xx / 5xx) and reduce the body
 * to a leak-free `{ success, message }` envelope.  Cookie forwarding mirrors
 * `lib/server/api/score-submission.ts`.
 */

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

/** The four checkboxes plus the optional free-text "Other" description. */
export interface UserReportRequest {
  offending_username: string;
  reason_username: boolean;
  reason_name: boolean;
  reason_bio: boolean;
  reason_other: boolean;
  other_description: string;
}

/** Upstream acknowledgement after a report is filed or merged. */
export interface UserReportResponse {
  success: boolean;
  message: string;
}

/** Caller context for the forced-username remediation form. */
export interface RemediationContext {
  username: string;
  email: string;
}

export interface UsernameRemediationRequest {
  new_username: string;
  new_password: string;
  confirm_password: string;
}

export interface UsernameRemediationResponse {
  success: boolean;
  username: string;
  message: string;
}

/** The authenticated caller's lockout state (SBGC-223). */
export interface LockoutStatus {
  status: string | null;
  username: string | null;
}

export interface SecurityRequestOptions {
  /** Viewer `sessionid` cookie value, forwarded so Django can authenticate. */
  sessionId?: string;
  signal?: AbortSignal;
}

/** The upstream outcome: the exact status plus its parsed body. */
export type UpstreamResult<T> =
  | { ok: true; statusCode: number; data: T }
  | { ok: false; statusCode: number; data: unknown };

function buildHeaders(options: SecurityRequestOptions, json: boolean): Headers {
  const headers = new Headers({ Accept: "application/json" });
  if (json) headers.set("Content-Type", "application/json");
  if (options.sessionId) {
    headers.set("Cookie", `sessionid=${options.sessionId}`);
  }
  return headers;
}

async function readBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function call<T>(
  path: string,
  init: { method: string; payload?: unknown },
  options: SecurityRequestOptions,
): Promise<UpstreamResult<T>> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    method: init.method,
    headers: buildHeaders(options, init.payload !== undefined),
    body: init.payload === undefined ? null : JSON.stringify(init.payload),
    signal: options.signal,
  });

  const data = await readBody(response);
  if (response.ok) {
    return { ok: true, statusCode: response.status, data: data as T };
  }
  return { ok: false, statusCode: response.status, data };
}

/** File or merge a user report against another account. */
export function submitUserReport(
  payload: UserReportRequest,
  options: SecurityRequestOptions = {},
): Promise<UpstreamResult<UserReportResponse>> {
  return call<UserReportResponse>(
    "/api/v1/security/reports/user",
    { method: "POST", payload },
    options,
  );
}

/** Fetch the caller's lockout status.  Returns `null` on any failure. */
export async function getModerationLockout(
  options: SecurityRequestOptions = {},
): Promise<LockoutStatus | null> {
  try {
    const result = await call<LockoutStatus>(
      "/api/v1/security/lockout",
      { method: "GET" },
      options,
    );
    if (!result.ok) return null;
    return result.data;
  } catch {
    // Fail open: a backend outage must never lock every session out of the
    // site.  The page renders normally and enforcement resumes on recovery.
    return null;
  }
}

/** Fetch the forced-username remediation context for a locked-out caller. */
export function getRemediationContext(
  options: SecurityRequestOptions = {},
): Promise<UpstreamResult<RemediationContext>> {
  return call<RemediationContext>(
    "/api/v1/security/remediate/username",
    { method: "GET" },
    options,
  );
}

/** Apply a forced username + password rotation. */
export function submitUsernameRemediation(
  payload: UsernameRemediationRequest,
  options: SecurityRequestOptions = {},
): Promise<UpstreamResult<UsernameRemediationResponse>> {
  return call<UsernameRemediationResponse>(
    "/api/v1/security/remediate/username",
    { method: "POST", payload },
    options,
  );
}
