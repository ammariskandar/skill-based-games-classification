import type { APIRoute } from "astro";

import { submitGameSuggestion } from "../../lib/server/api/suggestions";
import { getTrustedClientIp } from "../../lib/server/trusted-client-ip";

/**
 * Game-suggestion BFF proxy — SBGC-240.
 *
 * The browser never posts to Django directly: this SSR endpoint reads the
 * caller's HttpOnly `sessionid`, forwards the edge-resolved client IP, relays
 * the suggestion server-to-server, and reduces the upstream body to a
 * leak-free `{ success, message }` / `{ error }` envelope.
 *
 * Field limits are enforced here as a fast pre-flight only — Django re-validates
 * authoritatively and its verdict is what the browser ultimately sees.
 *
 * `Retry-After` from an upstream 429 is relayed untouched so the modal can sync
 * its cooldown to the same window the server is enforcing.
 */

export const prerender = false;

const MAX_NAME_LENGTH = 50;
const MAX_URL_LENGTH = 250;
const MAX_REMARKS_LENGTH = 250;

function json(
  body: unknown,
  status: number,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function errorResponse(
  code: string,
  message: string,
  status: number,
): Response {
  return json({ error: { code, message } }, status);
}

function asTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/** An https-only URL check: rejects `http:`, `javascript:`, `data:`, and junk. */
function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

function extractUpstreamError(
  data: unknown,
  statusCode: number,
): { error: { code: string; message: string } } {
  if (data && typeof data === "object" && "error" in data) {
    const error = (data as { error?: unknown }).error;
    if (error && typeof error === "object") {
      const code = (error as { code?: unknown }).code;
      const message = (error as { message?: unknown }).message;
      if (typeof code === "string" && typeof message === "string") {
        return { error: { code, message } };
      }
    }
  }
  if (statusCode === 429) {
    return {
      error: {
        code: "RATE_LIMITED",
        message: "Please wait a moment before submitting another suggestion.",
      },
    };
  }
  return {
    error: {
      code: statusCode === 401 ? "UNAUTHENTICATED" : "SUGGESTION_FAILED",
      message: "We couldn't send your suggestion. Please try again.",
    },
  };
}

export const POST: APIRoute = async ({ request, cookies }) => {
  const sessionId = cookies.get("sessionid")?.value;
  if (!sessionId) {
    return errorResponse("UNAUTHENTICATED", "Login required.", 401);
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("BAD_REQUEST", "Malformed suggestion payload.", 400);
  }

  const name = asTrimmedString(body.name);
  const storefrontUrl = asTrimmedString(body.storefront_url);
  const remarks = asTrimmedString(body.remarks);

  if (!name) {
    return errorResponse("VALIDATION_ERROR", "A game name is required.", 422);
  }
  if (name.length > MAX_NAME_LENGTH) {
    return errorResponse(
      "VALIDATION_ERROR",
      `Game name cannot exceed ${MAX_NAME_LENGTH} characters.`,
      422,
    );
  }
  if (storefrontUrl.length > MAX_URL_LENGTH) {
    return errorResponse(
      "VALIDATION_ERROR",
      `Storefront URL cannot exceed ${MAX_URL_LENGTH} characters.`,
      422,
    );
  }
  if (storefrontUrl && !isHttpsUrl(storefrontUrl)) {
    return errorResponse(
      "VALIDATION_ERROR",
      "The storefront link must be a valid https:// URL.",
      422,
    );
  }
  if (remarks.length > MAX_REMARKS_LENGTH) {
    return errorResponse(
      "VALIDATION_ERROR",
      `Remarks cannot exceed ${MAX_REMARKS_LENGTH} characters.`,
      422,
    );
  }

  try {
    const result = await submitGameSuggestion(
      { name, storefront_url: storefrontUrl, remarks },
      {
        sessionId,
        clientIp: getTrustedClientIp(request),
        signal: request.signal,
      },
    );

    if (result.ok) {
      return json(
        {
          success: true,
          message: "Thanks — your suggestion has been sent.",
        },
        200,
      );
    }

    const headers: Record<string, string> = {};
    if (result.statusCode === 429) {
      // Relay the server's own window so the client countdown matches it.
      headers["Retry-After"] = result.retryAfter ?? "60";
    }
    return json(
      extractUpstreamError(result.data, result.statusCode),
      result.statusCode,
      headers,
    );
  } catch {
    return errorResponse(
      "SERVICE_UNAVAILABLE",
      "The suggestion service is temporarily unreachable.",
      503,
    );
  }
};
