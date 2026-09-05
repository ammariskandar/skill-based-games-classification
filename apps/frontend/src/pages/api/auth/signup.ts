import type { APIRoute } from "astro";

/**
 * Astro BFF signup proxy — SBGC-218.
 *
 * Relays the verified registration payload server-to-server.  On 201 Created,
 * persists Django's `sessionid` as an HttpOnly cookie (auto-login) and sets
 * the ephemeral welcome toast.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const POST: APIRoute = async ({ request, cookies }) => {
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
    const backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Forwarded-For":
          request.headers.get("x-forwarded-for") || "127.0.0.1",
      },
      body: JSON.stringify(body),
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return new Response(JSON.stringify(data), {
        status: backendRes.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Auto-login: relay Django's sessionid cookie.
    const rawSetCookie = backendRes.headers.get("set-cookie");
    if (rawSetCookie) {
      const match = rawSetCookie.match(/sessionid=([^;]+)/);
      if (match) {
        cookies.set("sessionid", match[1], {
          path: "/",
          httpOnly: true,
          sameSite: "lax",
          secure: import.meta.env.PROD,
        });
      }
    }

    cookies.set("flash_toast", "signup_success", {
      path: "/",
      maxAge: 5,
      sameSite: "lax",
      httpOnly: false,
    });

    return new Response(JSON.stringify(data), {
      status: 201,
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
