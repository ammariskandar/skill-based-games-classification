/**
 * Global SSR middleware — SBGC-109 / SBGC-223.
 *
 * 1. Strips server-identification banner headers (`Server`, `X-Powered-By`)
 *    from every server-rendered response so the Astro runtime never advertises
 *    its framework, Node runtime, or an underlying Express-style server.  The
 *    rule lives in `lib/server/banner-headers.ts` so it is unit-testable
 *    without the Astro virtual module.
 * 2. Enforces moderation lockouts for authenticated users: a username lockout
 *    is funnelled to `/remediate/username`, and a name/bio lockout to the
 *    viewer's own profile where the forced Edit Profile modal runs.  The
 *    backend remains authoritative; this only chooses the surface.
 */
import { defineMiddleware } from "astro:middleware";

import { stripServerIdentificationHeaders } from "./lib/server/banner-headers";
import {
  isPageRequest,
  moderationRedirect,
} from "./lib/server/moderation-routing";
import { getModerationLockout } from "./lib/server/api/security";

export const onRequest = defineMiddleware(async (context, next) => {
  const sessionId = context.cookies.get("sessionid")?.value;

  if (sessionId && isPageRequest(context.url.pathname)) {
    const lockout = await getModerationLockout({ sessionId });
    if (lockout?.status) {
      const target = moderationRedirect({
        pathname: context.url.pathname,
        status: lockout.status,
        username: lockout.username,
      });
      if (target) {
        return context.redirect(target, 302);
      }
    }
  }

  const response = await next();
  if (response) {
    stripServerIdentificationHeaders(response.headers);
  }
  return response;
});
