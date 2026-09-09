import type { APIRoute } from "astro";

import { parseAndValidateBbCode } from "../../../lib/bbcode";
import { validateContentSecurity } from "../../../lib/content-security";

/**
 * Astro BFF profile-update proxy — SBGC-222.
 *
 * The browser never talks to Django directly: this SSR endpoint runs the
 * content-security and BBCode sweeps locally, then relays the clean payload
 * server-to-server using the viewer's session cookie.
 */

export const prerender = false;

const BACKEND_URL = import.meta.env.DJANGO_API_URL || "http://127.0.0.1:8000";

function errorResponse(
  code: string,
  message: string,
  status: number,
): Response {
  return new Response(
    JSON.stringify({ error: { code, message, details: [] } }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

export const POST: APIRoute = async ({ request, cookies }) => {
  const sessionid = cookies.get("sessionid")?.value;
  if (!sessionid) {
    return errorResponse("AUTHENTICATION_ERROR", "Unauthorized", 401);
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return errorResponse("VALIDATION_ERROR", "Malformed JSON payload", 400);
  }

  const first_name = typeof body.first_name === "string" ? body.first_name : "";
  const last_name = typeof body.last_name === "string" ? body.last_name : "";
  const bio = typeof body.bio === "string" ? body.bio : "";
  const bio_mode = typeof body.bio_mode === "string" ? body.bio_mode : "PLAIN";
  const avatar_key =
    typeof body.avatar_key === "string" ? body.avatar_key : "male_1";
  const border_type =
    typeof body.border_type === "string" ? body.border_type : "NONE";
  const border_preset_id =
    typeof body.border_preset_id === "number" ? body.border_preset_id : null;
  const border_color =
    typeof body.border_color === "string" ? body.border_color : "";

  if (first_name.length > 100 || last_name.length > 100) {
    return errorResponse(
      "VALIDATION_ERROR",
      "Name fields cannot exceed 100 characters.",
      422,
    );
  }

  const mode = bio_mode === "BBCODE" ? "BBCODE" : "PLAIN";

  const securityCheck = validateContentSecurity(bio, mode);
  if (!securityCheck.isValid) {
    return errorResponse(
      "VALIDATION_ERROR",
      securityCheck.error ?? "Invalid bio",
      422,
    );
  }

  if (mode === "BBCODE" && bio) {
    const bbCodeCheck = parseAndValidateBbCode(bio);
    if (!bbCodeCheck.isValid) {
      return errorResponse(
        "VALIDATION_ERROR",
        bbCodeCheck.error ?? "Invalid bio",
        422,
      );
    }
  } else if (mode === "PLAIN" && bio.length > 250) {
    return errorResponse(
      "VALIDATION_ERROR",
      "Plain text bio cannot exceed 250 characters.",
      422,
    );
  }

  try {
    const backendRes = await fetch(`${BACKEND_URL}/api/v1/users/me`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Cookie: `sessionid=${sessionid}`,
        "X-Forwarded-For":
          request.headers.get("x-forwarded-for") || "127.0.0.1",
      },
      body: JSON.stringify({
        first_name,
        last_name,
        bio,
        bio_mode: mode,
        avatar_key,
        border_type,
        border_preset_id,
        border_color,
      }),
    });

    const data = await backendRes.json();
    return new Response(JSON.stringify(data), {
      status: backendRes.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return errorResponse(
      "SERVICE_UNAVAILABLE",
      "Profile service is temporarily unreachable.",
      503,
    );
  }
};
