import type { APIRoute } from "astro";

/**
 * Astro BFF verification-status proxy — SBGC-218.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const GET: APIRoute = async ({ url }) => {
  const challengeId = url.searchParams.get("challenge_id") ?? "";
  try {
    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/auth/verification-status?challenge_id=${encodeURIComponent(challengeId)}`,
      { headers: { Accept: "application/json" } },
    );
    const data = await backendRes.json();
    return new Response(JSON.stringify(data), {
      status: backendRes.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return new Response(JSON.stringify({ verified: false }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
};
