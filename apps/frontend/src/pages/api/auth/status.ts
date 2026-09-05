import type { APIRoute } from "astro";

/**
 * Astro BFF status proxy — SBGC-217.
 *
 * Reads the browser's `sessionid` and relays it to Django's status endpoint.
 * Never returns a cookie or credential to the client — only the public
 * `{ authenticated, username }` shape.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const GET: APIRoute = async ({ cookies }) => {
  const sessionId = cookies.get("sessionid")?.value;

  const unauthResponse = () =>
    new Response(JSON.stringify({ authenticated: false, username: null }), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });

  if (!sessionId) {
    return unauthResponse();
  }

  try {
    const backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/status`, {
      headers: { Cookie: `sessionid=${sessionId}` },
    });

    if (!backendRes.ok) {
      return unauthResponse();
    }

    const data = await backendRes.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return unauthResponse();
  }
};
