/**
 * Manual score-submission API boundary — SBGC-225.
 *
 * Server-side only (Astro API routes).  Uses raw `fetch` rather than the shared
 * `client.ts` transport because the BFF must relay the exact upstream status
 * (201 created / 200 updated-or-duplicate / 4xx / 5xx) and body to the browser
 * so the modal can branch on the SBGC-216 temporal outcome.  Cookie forwarding
 * mirrors `lib/server/api/questionnaire.ts`.
 */

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

/** One three-dimensional profile sent by the manual form. */
export interface ManualScoreProfile {
  micro: number;
  mystiko: number;
  macro: number;
}

/** `POST /api/v1/classifications/games/{slug}/submit-score` request body. */
export interface ManualScoreSubmissionRequest {
  challenge: ManualScoreProfile;
  reward: ManualScoreProfile;
  aesthetic: string;
  secondary_aesthetic?: string | null;
}

/** Success body returned by the SBGC-216 ingestion pipeline. */
export interface ManualScoreSubmissionResponse {
  id: number;
  game_slug: string;
  aesthetic: string | null;
  secondary_aesthetic: string | null;
  is_duplicate: boolean;
  is_updated: boolean;
  is_created: boolean;
  submitted_at: string;
}

export interface ManualScoreRequestOptions {
  /** Viewer `sessionid` cookie value, forwarded so Django can authenticate. */
  sessionId?: string;
  signal?: AbortSignal;
}

/** The upstream outcome: the exact status plus its parsed body. */
export type ManualScoreSubmissionResult =
  | { ok: true; statusCode: number; data: ManualScoreSubmissionResponse }
  | { ok: false; statusCode: number; data: unknown };

function buildHeaders(
  options: ManualScoreRequestOptions,
  json: boolean,
): Headers {
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

/**
 * Submit a manual Challenge/Reward score for one Game.
 *
 * Never throws for an HTTP error response — the status and body are returned so
 * the BFF can relay them.  A transport failure (Django unreachable) throws,
 * which the BFF maps to a 500.
 */
export async function submitManualScore(
  slug: string,
  payload: ManualScoreSubmissionRequest,
  options: ManualScoreRequestOptions = {},
): Promise<ManualScoreSubmissionResult> {
  const response = await fetch(
    `${BACKEND_URL}/api/v1/classifications/games/${encodeURIComponent(slug)}/submit-score`,
    {
      method: "POST",
      headers: buildHeaders(options, true),
      body: JSON.stringify(payload),
      signal: options.signal,
    },
  );

  const data = await readBody(response);
  if (response.ok) {
    return {
      ok: true,
      statusCode: response.status,
      data: data as ManualScoreSubmissionResponse,
    };
  }
  return { ok: false, statusCode: response.status, data };
}
