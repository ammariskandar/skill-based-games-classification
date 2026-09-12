import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getAuthStatus,
  getModerationLockout,
  submitUsernameRemediation,
} from "../security";

/**
 * SBGC-223 moderation boundary tests.
 *
 * The remediation flow must surface Django's rotated `sessionid` `Set-Cookie`
 * header: the endpoint cycles the session key on password rotation, so dropping
 * the header silently logs the freshly-remediated user out.
 */

function stubFetch(
  body: unknown,
  {
    status = 200,
    setCookie = null,
  }: { status?: number; setCookie?: string | null } = {},
) {
  const requests: RequestInit[] = [];
  const fetchMock = vi.fn(
    async (url: unknown, init?: RequestInit): Promise<unknown> => {
      void url;
      if (init) requests.push(init);
      return {
        ok: status >= 200 && status < 300,
        status,
        headers: {
          get: (name: string) =>
            name.toLowerCase() === "set-cookie" ? setCookie : null,
        },
        json: async () => body,
      };
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("submitUsernameRemediation", () => {
  it("surfaces the upstream rotated session cookie", async () => {
    stubFetch(
      { success: true, username: "clean-name", message: "ok" },
      { setCookie: "sessionid=abc123; Path=/; HttpOnly; SameSite=Lax" },
    );

    const result = await submitUsernameRemediation(
      {
        new_username: "clean-name",
        new_password: "fresh-password",
        confirm_password: "fresh-password",
      },
      { sessionId: "stale" },
    );

    expect(result.ok).toBe(true);
    expect(result.setCookie).toContain("sessionid=abc123");
  });

  it("forwards the caller's session cookie to Django", async () => {
    const requests = stubFetch({ success: true, username: "x", message: "ok" });

    await submitUsernameRemediation(
      {
        new_username: "clean-name",
        new_password: "fresh-password",
        confirm_password: "fresh-password",
      },
      { sessionId: "caller-session" },
    );

    const headers = requests[0]?.headers as Headers;
    expect(headers.get("Cookie")).toBe("sessionid=caller-session");
  });

  it("reports a validation failure without a cookie", async () => {
    stubFetch(
      {
        error: {
          code: "VALIDATION_ERROR",
          message: "Choose a different username.",
        },
      },
      { status: 422 },
    );

    const result = await submitUsernameRemediation(
      {
        new_username: "same",
        new_password: "fresh-password",
        confirm_password: "fresh-password",
      },
      { sessionId: "x" },
    );

    expect(result.ok).toBe(false);
    expect(result.statusCode).toBe(422);
    expect(result.setCookie).toBeNull();
  });
});

describe("getAuthStatus", () => {
  it("returns the parsed authentication state", async () => {
    stubFetch({ authenticated: true, username: "james" });
    await expect(getAuthStatus({ sessionId: "good" })).resolves.toEqual({
      authenticated: true,
      username: "james",
    });
  });

  it("returns null for a stale or invalid session", async () => {
    stubFetch(
      { error: { code: "AUTHENTICATION_ERROR", message: "no" } },
      { status: 401 },
    );
    await expect(getAuthStatus({ sessionId: "stale" })).resolves.toBeNull();
  });
});

describe("getModerationLockout", () => {
  it("reads the lowercase lockout status", async () => {
    stubFetch({ status: "pending_bio_change", username: "james" });
    await expect(getModerationLockout({ sessionId: "good" })).resolves.toEqual({
      status: "pending_bio_change",
      username: "james",
    });
  });

  it("fails open when the backend is unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("connection refused");
      }),
    );
    await expect(
      getModerationLockout({ sessionId: "good" }),
    ).resolves.toBeNull();
  });
});
