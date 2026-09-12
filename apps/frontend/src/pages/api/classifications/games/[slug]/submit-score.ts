import type { APIRoute } from "astro";

import type { ManualScoreSubmissionRequest } from "../../../../../lib/server/api/score-submission";
import { submitManualScore } from "../../../../../lib/server/api/score-submission";

/**
 * Manual score-submission BFF proxy — SBGC-225.
 *
 * The browser posts to this relative endpoint only; the internal Django host is
 * never exposed to client bundles.  The viewer `sessionid` is read server-side
 * and forwarded, and the upstream status (201 created / 200 updated-or-duplicate
 * / 4xx / 5xx) plus body are relayed verbatim so the modal can branch on the
 * SBGC-216 temporal outcome.
 */
export const prerender = false;

export const POST: APIRoute = async ({ params, request, cookies }) => {
  const slug = params.slug;
  if (!slug) {
    return json(
      { error: { code: "BAD_REQUEST", message: "Game slug is required." } },
      400,
    );
  }

  const sessionId = cookies.get("sessionid")?.value;
  if (!sessionId) {
    return json(
      { error: { code: "UNAUTHENTICATED", message: "Login required." } },
      401,
    );
  }

  let payload: ManualScoreSubmissionRequest;
  try {
    payload = (await request.json()) as ManualScoreSubmissionRequest;
  } catch {
    return json(
      {
        error: {
          code: "BAD_REQUEST",
          message: "Malformed submission payload.",
        },
      },
      400,
    );
  }

  try {
    const result = await submitManualScore(slug, payload, { sessionId });
    return json(result.data ?? {}, result.statusCode);
  } catch {
    return json(
      {
        error: {
          code: "SUBMISSION_FAILED",
          message: "Internal submission error.",
        },
      },
      500,
    );
  }
};

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
