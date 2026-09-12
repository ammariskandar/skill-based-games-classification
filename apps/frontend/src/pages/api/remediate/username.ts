import type { APIRoute } from "astro";

import { submitUsernameRemediation } from "../../../lib/server/api/security";

/**
 * Forced-username remediation BFF proxy — SBGC-223.
 *
 * Relays the locked-out caller's username + password rotation to Django using
 * their HttpOnly `sessionid`.  The upstream envelope (200 rotated / 401 / 403 /
 * 422) is passed through verbatim so the locked page can render the exact
 * validation failure.
 */

export const prerender = false;

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const POST: APIRoute = async ({ request, cookies }) => {
  const sessionId = cookies.get("sessionid")?.value;
  if (!sessionId) {
    return json(
      { error: { code: "UNAUTHENTICATED", message: "Login required." } },
      401,
    );
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json(
      { error: { code: "BAD_REQUEST", message: "Malformed payload." } },
      400,
    );
  }

  const newUsername =
    typeof body.new_username === "string" ? body.new_username : "";
  const newPassword =
    typeof body.new_password === "string" ? body.new_password : "";
  const confirmPassword =
    typeof body.confirm_password === "string" ? body.confirm_password : "";

  try {
    const result = await submitUsernameRemediation(
      {
        new_username: newUsername,
        new_password: newPassword,
        confirm_password: confirmPassword,
      },
      { sessionId },
    );

    // Django cycles the session key when the password rotates and returns the
    // replacement `sessionid`.  Relay it, or the browser keeps the now-dead
    // cookie and the freshly-remediated user is silently logged out.
    const rotated = result.setCookie?.match(/sessionid=([^;]+)/);
    if (rotated) {
      cookies.set("sessionid", rotated[1], {
        path: "/",
        httpOnly: true,
        sameSite: "lax",
        secure: import.meta.env.PROD,
      });
    }

    return json(result.data ?? {}, result.statusCode);
  } catch {
    return json(
      {
        error: {
          code: "SERVICE_UNAVAILABLE",
          message: "The remediation service is temporarily unreachable.",
        },
      },
      503,
    );
  }
};
