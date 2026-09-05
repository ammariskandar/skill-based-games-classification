import type { APIRoute } from "astro";

/**
 * Astro BFF check-username proxy — SBGC-218.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const GET: APIRoute = async ({ url }) => {
  const username = url.searchParams.get("username") ?? "";
  try {
    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/auth/check-username?username=${encodeURIComponent(username)}`,
      { headers: { Accept: "application/json" } },
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
