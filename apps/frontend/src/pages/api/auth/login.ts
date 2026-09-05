import type { APIRoute } from "astro";

/**
 * Astro BFF login proxy — SBGC-217.
 *
 * The browser never talks to Django directly: this SSR endpoint relays the
 * credential payload server-to-server, then persists Django's opaque
 * `sessionid` as an HttpOnly cookie and sets the ephemeral success toast.
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
    const backendRes = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
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
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const retryAfter = backendRes.headers.get("retry-after");
      if (retryAfter) headers["Retry-After"] = retryAfter;
      return new Response(JSON.stringify(data), {
        status: backendRes.status,
        headers,
      });
    }

    // Capture Django's sessionid cookie and relay it to the browser.
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

    cookies.set("flash_toast", "login_success", {
      path: "/",
      maxAge: 5,
      sameSite: "lax",
      httpOnly: false,
    });

    return new Response(JSON.stringify(data), {
      status: 200,
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
