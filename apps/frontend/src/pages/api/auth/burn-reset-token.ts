import type { APIRoute } from "astro";

/**
 * Astro BFF burn-reset-token proxy — SBGC-219.
 *
 * Best-effort anti-abandonment invalidation fired from `navigator.sendBeacon`
 * when the human leaves a claimed reset page.  The browser sends beacons with
 * arbitrary content-types, so the body is parsed defensively (JSON or plain
 * text carrying a JSON payload).  A beacon response is never read by the
 * browser; a graceful 200 keeps the console clean even when the payload is
 * unparseable (the token still expires server-side within 15 minutes and can
 * never be claimed twice).
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

async function parseBody(request: Request): Promise<unknown> {
  const text = await request.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export const POST: APIRoute = async ({ request }) => {
  const body = await parseBody(request);
  if (!body) {
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/auth/burn-reset-token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
    const data = await backendRes.json();
    return new Response(JSON.stringify(data), {
      status: backendRes.status,
      headers: { "Content-Type": "application/json" },
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
