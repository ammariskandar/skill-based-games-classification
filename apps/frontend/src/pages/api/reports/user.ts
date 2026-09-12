import type { APIRoute } from "astro";

import { submitUserReport } from "../../../lib/server/api/security";

/**
 * User-report BFF proxy — SBGC-223.
 *
 * The browser never posts to Django directly: this SSR endpoint reads the
 * caller's HttpOnly `sessionid`, relays the report server-to-server, and
 * reduces the upstream body to a leak-free `{ success, message }` envelope
 * (no internal report/user IDs cross back to the client).
 */

export const prerender = false;

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(
  code: string,
  message: string,
  status: number,
): Response {
  return json({ error: { code, message } }, status);
}

function asBoolean(value: unknown): boolean {
  return value === true;
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
    return errorResponse("BAD_REQUEST", "Malformed report payload.", 400);
  }

  const offendingUsername =
    typeof body.offending_username === "string"
      ? body.offending_username.trim()
      : "";
  if (!offendingUsername) {
    return errorResponse("BAD_REQUEST", "A target user is required.", 400);
  }

  const reasons = {
    reason_username: asBoolean(body.reason_username),
    reason_name: asBoolean(body.reason_name),
    reason_bio: asBoolean(body.reason_bio),
    reason_other: asBoolean(body.reason_other),
  };

  const otherDescription =
    typeof body.other_description === "string" ? body.other_description : "";

  if (!Object.values(reasons).some(Boolean)) {
    return errorResponse(
      "VALIDATION_ERROR",
      "Select at least one reason.",
      422,
    );
  }
  if (otherDescription.length > 250) {
    return errorResponse(
      "VALIDATION_ERROR",
      "Other details cannot exceed 250 characters.",
      422,
    );
  }
  if (otherDescription.includes("<") || otherDescription.includes(">")) {
    return errorResponse(
      "VALIDATION_ERROR",
      "Angle brackets are not allowed.",
      422,
    );
  }

  try {
    const result = await submitUserReport(
      {
        offending_username: offendingUsername,
        ...reasons,
        other_description: otherDescription,
      },
      { sessionId },
    );

    if (result.ok) {
      return json(
        { success: true, message: "Report submitted successfully." },
        200,
      );
    }

    return json(
      extractUpstreamError(result.data, result.statusCode),
      result.statusCode,
    );
  } catch {
    return errorResponse(
      "SERVICE_UNAVAILABLE",
      "The reporting service is temporarily unreachable.",
      503,
    );
  }
};

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
  return {
    error: {
      code: statusCode === 401 ? "UNAUTHENTICATED" : "REPORT_FAILED",
      message: "We couldn't submit your report. Please try again.",
    },
  };
}
