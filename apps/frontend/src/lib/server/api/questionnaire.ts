/**
 * Questionnaire session + submission API boundary — SBGC-176.
 *
 * Server-side only (Astro frontmatter / API routes).  Uses raw `fetch` rather
 * than the shared `client.ts` transport because the HTTP 409 conflict response
 * carries a non-envelope body (`{ error, message, precedence }`) that the
 * `ApiResult` abstraction cannot surface.  Cookie forwarding mirrors the BFF
 * pattern in `pages/api/auth/status.ts`.
 */

import type {
  ConflictRequiredResponse,
  QuestionnaireSessionResponse,
  QuestionnaireSubmitRequest,
  QuestionnaireSubmitResponse,
} from "../../questionnaire/types";

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export interface QuestionnaireRequestOptions {
  /** Viewer `sessionid` cookie value, forwarded so Django can authenticate. */
  sessionId?: string;
  signal?: AbortSignal;
}

/** A non-2xx questionnaire response other than the 409 conflict contract. */
export class QuestionnaireApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "QuestionnaireApiError";
    this.status = status;
  }
}

function buildHeaders(
  options: QuestionnaireRequestOptions,
  json: boolean,
): Headers {
  const headers = new Headers({ Accept: "application/json" });
  if (json) headers.set("Content-Type", "application/json");
  if (options.sessionId)
    headers.set("Cookie", `sessionid=${options.sessionId}`);
  return headers;
}

async function errorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const body = (await response.json()) as {
      message?: string;
      error?: { message?: string } | string;
    };
    if (typeof body.message === "string") return body.message;
    if (typeof body.error === "object" && body.error?.message) {
      return body.error.message;
    }
    return fallback;
  } catch {
    return fallback;
  }
}

/** Fetch the authenticated questionnaire session for one Game. */
export async function getQuestionnaireSession(
  slug: string,
  options: QuestionnaireRequestOptions = {},
): Promise<QuestionnaireSessionResponse> {
  const response = await fetch(
    `${BACKEND_URL}/api/v1/questionnaire/${encodeURIComponent(slug)}/session`,
    { headers: buildHeaders(options, false), signal: options.signal },
  );

  if (!response.ok) {
    throw new QuestionnaireApiError(
      await errorMessage(
        response,
        `Failed to load questionnaire session (${response.status})`,
      ),
      response.status,
    );
  }
  return (await response.json()) as QuestionnaireSessionResponse;
}

/** Result of a questionnaire submission, discriminating the 409 conflict. */
export type SubmitQuestionnaireResult =
  | { type: "success"; data: QuestionnaireSubmitResponse; statusCode: number }
  | { type: "conflict"; data: ConflictRequiredResponse };

/** Submit a completed questionnaire traversal for authoritative persistence. */
export async function submitQuestionnaire(
  slug: string,
  payload: QuestionnaireSubmitRequest,
  options: QuestionnaireRequestOptions = {},
): Promise<SubmitQuestionnaireResult> {
  const response = await fetch(
    `${BACKEND_URL}/api/v1/questionnaire/${encodeURIComponent(slug)}/submit`,
    {
      method: "POST",
      headers: buildHeaders(options, true),
      body: JSON.stringify(payload),
      signal: options.signal,
    },
  );

  if (response.status === 409) {
    return {
      type: "conflict",
      data: (await response.json()) as ConflictRequiredResponse,
    };
  }
  if (!response.ok) {
    throw new QuestionnaireApiError(
      await errorMessage(response, `Submission failed (${response.status})`),
      response.status,
    );
  }
  return {
    type: "success",
    data: (await response.json()) as QuestionnaireSubmitResponse,
    statusCode: response.status,
  };
}
