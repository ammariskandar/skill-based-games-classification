/**
 * Game-suggestion API boundary — SBGC-240.
 *
 * Server-side only (Astro API routes).  Uses raw `fetch` rather than the shared
 * `client.ts` transport because the suggestion BFF must relay the exact upstream
 * outcome back to the browser: a 200 acknowledgement, or a 429 whose
 * `Retry-After` drives the modal's cooldown timer.  Cookie forwarding mirrors
 * `lib/server/api/security.ts`.
 *
 * The upstream call carries the viewer's session and the edge-resolved client
 * IP, so Django owns authentication and both throttle buckets.
 */

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export interface GameSuggestionRequest {
  name: string;
  storefront_url: string;
  remarks: string;
}

export interface GameSuggestionResponse {
  success: boolean;
  message: string;
}

export interface SuggestionRequestOptions {
  /** Viewer `sessionid` cookie value, forwarded so Django can authenticate. */
  sessionId?: string;
  /** Edge-resolved client IP, forwarded for the per-IP throttle bucket. */
  clientIp?: string;
  signal?: AbortSignal;
}

/** The upstream outcome: the exact status plus its parsed body. */
export type SuggestionUpstreamResult =
  | { ok: true; statusCode: number; data: GameSuggestionResponse }
  | {
      ok: false;
      statusCode: number;
      data: unknown;
      retryAfter: string | null;
    };

/**
 * Send a validated game suggestion to Django.
 *
 * Throws only on transport failure; every HTTP status (including 4xx/5xx) comes
 * back as a result so the BFF can relay it verbatim.
 */
export async function submitGameSuggestion(
  payload: GameSuggestionRequest,
  options: SuggestionRequestOptions = {},
): Promise<SuggestionUpstreamResult> {
  const headers = new Headers({
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  if (options.sessionId) {
    headers.set("Cookie", `sessionid=${options.sessionId}`);
  }
  if (options.clientIp) {
    headers.set("X-Client-Real-IP", options.clientIp);
  }

  const response = await fetch(`${BACKEND_URL}/api/v1/suggestions/`, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  const data: unknown = await response.json().catch(() => null);

  if (response.ok) {
    return {
      ok: true,
      statusCode: response.status,
      data: data as GameSuggestionResponse,
    };
  }

  return {
    ok: false,
    statusCode: response.status,
    data,
    retryAfter: response.headers.get("retry-after"),
  };
}
