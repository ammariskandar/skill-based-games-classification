import type { APIRoute } from "astro";

import {
  QuestionnaireApiError,
  getQuestionnaireSession,
} from "../../../../lib/server/api/questionnaire";

/**
 * Questionnaire session BFF proxy — SBGC-225.
 *
 * Lets the client-side submission modal perform the precedence pre-check
 * (does the viewer already have an active questionnaire for this Game?) without
 * exposing the internal backend host.  The viewer `sessionid` is read
 * server-side and forwarded; a missing cookie short-circuits to 401.
 */
export const prerender = false;

export const GET: APIRoute = async ({ params, cookies }) => {
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

  try {
    const session = await getQuestionnaireSession(slug, { sessionId });
    return json(session, 200);
  } catch (error: unknown) {
    if (error instanceof QuestionnaireApiError) {
      return json(
        { error: { code: "SESSION_UNAVAILABLE", message: error.message } },
        error.status,
      );
    }
    return json(
      {
        error: {
          code: "SESSION_UNAVAILABLE",
          message: "Unable to load the questionnaire session.",
        },
      },
      502,
    );
  }
};

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
