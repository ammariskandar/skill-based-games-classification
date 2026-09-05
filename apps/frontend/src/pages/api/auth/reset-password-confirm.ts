import type { APIRoute } from "astro";

/**
 * Astro BFF reset-password-confirm proxy — SBGC-219.
 *
 * Relays the one-chance nonce + new password server-to-server.  On 200 OK it
 * sets the ephemeral `flash_toast=password_reset_success` cookie so the home
 * page shows the "password reset" toast after the redirect.  No session cookie
 * is set — a password reset deliberately does not auto-log-in.
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
    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/auth/reset-password-confirm`,
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

    if (!backendRes.ok) {
      return new Response(JSON.stringify(data), {
        status: backendRes.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 5-second ephemeral toast, read (and cleared) by the client Toast island.
    cookies.set("flash_toast", "password_reset_success", {
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
