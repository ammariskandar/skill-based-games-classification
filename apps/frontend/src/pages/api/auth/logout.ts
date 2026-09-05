import type { APIRoute } from "astro";

/**
 * Astro BFF logout proxy — SBGC-217.
 *
 * Forwards the logout to Django (relaying the `sessionid`), clears the local
 * session cookie regardless of upstream availability, sets the ephemeral
 * logout toast, and redirects home.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

export const POST: APIRoute = async ({ cookies, redirect }) => {
  const sessionId = cookies.get("sessionid")?.value;

  try {
    if (sessionId) {
      await fetch(`${BACKEND_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: { Cookie: `sessionid=${sessionId}` },
      });
    }
  } catch {
    // Fail-safe: clear the local session even if the upstream is unreachable.
  }

  cookies.delete("sessionid", { path: "/" });

  cookies.set("flash_toast", "logout_success", {
    path: "/",
    maxAge: 5,
    sameSite: "lax",
    httpOnly: false,
  });

  return redirect("/", 303);
};
