import type { APIRoute } from "astro";

import { getTrustedClientIp } from "../../../lib/server/trusted-client-ip";
import { containsProfanity } from "../../../lib/profanity";

/**
 * Astro BFF check-username proxy — SBGC-218 / SBGC-107.
 *
 * SBGC-107: the client IP is derived from the verified edge header and
 * forwarded as `X-Client-Real-IP`; `Retry-After` and the circuit-breaker
 * marker are relayed back so the sign-up page can escalate correctly.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const GET: APIRoute = async ({ request, url }) => {
  const username = url.searchParams.get("username") ?? "";
  if (containsProfanity(username)) {
    return new Response(JSON.stringify({ available: false }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  const clientIp = request ? getTrustedClientIp(request) : "127.0.0.1";
  try {
    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/auth/check-username?username=${encodeURIComponent(username)}`,
      {
        headers: {
          Accept: "application/json",
          "X-Client-Real-IP": clientIp,
        },
      },
    );
    const data = await backendRes.json();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const retryAfter = backendRes.headers.get("retry-after");
    if (retryAfter) headers["Retry-After"] = retryAfter;
    const circuitBreaker = backendRes.headers.get("x-circuit-breaker");
    if (circuitBreaker) headers["X-Circuit-Breaker"] = circuitBreaker;
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
