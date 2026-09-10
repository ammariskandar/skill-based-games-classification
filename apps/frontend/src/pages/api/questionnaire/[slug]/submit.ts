import type { APIRoute } from "astro";

import { submitQuestionnaire } from "../../../../lib/server/api/questionnaire";
import type { QuestionnaireSubmitRequest } from "../../../../lib/questionnaire/types";

/**
 * Questionnaire submission BFF proxy — SBGC-178.
 *
 * The browser posts to this relative endpoint only; the internal backend host
 * and paths are never exposed to client bundles.  The viewer `sessionid` is
 * read server-side and forwarded to Django.
 */
export const prerender = false;

export const POST: APIRoute = async ({ params, request, cookies }) => {
  const slug = params.slug;
  if (!slug) {
    return json({ error: "Missing game slug" }, 400);
  }

  const sessionId = cookies.get("sessionid")?.value;
  if (!sessionId) {
    return json({ error: "Authentication required" }, 401);
  }

  let payload: QuestionnaireSubmitRequest;
  try {
    payload = (await request.json()) as QuestionnaireSubmitRequest;
  } catch {
    return json({ error: "Malformed submission payload" }, 400);
  }

  try {
    const result = await submitQuestionnaire(slug, payload, { sessionId });
    if (result.type === "conflict") {
      return json(result.data, 409);
    }
    return json(result.data, result.statusCode);
  } catch {
    return json({ error: "Unable to process questionnaire submission" }, 500);
  }
};

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
