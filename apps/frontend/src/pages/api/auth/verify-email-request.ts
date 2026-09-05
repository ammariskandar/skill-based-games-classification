import type { APIRoute } from "astro";

/**
 * Astro BFF verify-email-request proxy — SBGC-218.
 *
 * Relays the email + reCAPTCHA token server-to-server, forwarding the client
 * IP and the 30-minute `Retry-After` hint when the backend rate-limits.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const POST: APIRoute = async ({ request }) => {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({
        error: {
          code: "VALIDATION_ERROR",
          message: "Malformed JSON payload.",
          details: [],
        },
      }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/auth/verify-email-request`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Forwarded-For":
            request.headers.get("x-forwarded-for") || "127.0.0.1",
        },
        body: JSON.stringify(body),
      },
    );
    const data = await backendRes.json();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const retryAfter = backendRes.headers.get("retry-after");
    if (retryAfter) headers["Retry-After"] = retryAfter;
    return new Response(JSON.stringify(data), {
      status: backendRes.status,
      headers,
    });
  } catch {
    return new Response(
      JSON.stringify({
        error: {
          code: "SERVICE_UNAVAILABLE",
          message: "Authentication service is temporarily unreachable.",
          details: [],
        },
      }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }
};
