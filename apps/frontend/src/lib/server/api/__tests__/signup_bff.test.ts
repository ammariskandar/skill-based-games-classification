/**
 * Sign-up BFF proxy tests — SBGC-218.
 *
 * Exercises the Astro API route handlers for check-username,
 * verify-email-request, verification-status, confirm-email, and signup as
 * plain modules (invoked with a minimal APIContext stand-in).  No real
 * network — `globalThis.fetch` is stubbed.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

interface CookieRecord {
  value: string;
  options?: Record<string, unknown>;
}

class FakeCookies {
  private store = new Map<string, CookieRecord>();
  readonly setCalls: Array<{
    name: string;
    value: string;
    options?: Record<string, unknown>;
  }> = [];

  get(name: string): { value: string } | undefined {
    const record = this.store.get(name);
    return record ? { value: record.value } : undefined;
  }

  set(name: string, value: string, options?: Record<string, unknown>): void {
    this.store.set(name, { value, options });
    this.setCalls.push({ name, value, options });
  }
}

function jsonRequest(
  payload: unknown,
  url = "http://test/api/auth/signup",
): Request {
  return new Request(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function jsonBackendResponse(
  body: unknown,
  status: number,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

beforeEach(() => {
  vi.stubEnv("DJANGO_API_URL", "http://127.0.0.1:8000");
  vi.resetModules();
});

describe("BFF check-username", () => {
  it("relays the username query and returns availability", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonBackendResponse({ available: true, username: "freeuser" }, 200),
        ),
    );

    const { GET } = await import("../../../../pages/api/auth/check-username");
    const response = await GET({
      url: new URL("http://test/api/auth/check-username?username=freeuser"),
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      available: true,
      username: "freeuser",
    });
    expect(
      (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0],
    ).toContain("check-username?username=freeuser");
  });
});

describe("BFF verify-email-request", () => {
  it("relays the payload with the client IP header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonBackendResponse(
          { challenge_id: "abc", message: "Verification email sent." },
          200,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { POST } =
      await import("../../../../pages/api/auth/verify-email-request");
    const response = await POST({
      request: jsonRequest(
        { email: "a@b.com", recaptcha_token: "t" },
        "http://test/api/auth/verify-email-request",
      ),
    } as never);

    expect(response.status).toBe(200);
    const call = fetchMock.mock.calls[0][1] as RequestInit;
    expect(call.headers).toMatchObject({ "X-Forwarded-For": "127.0.0.1" });
  });
});

describe("BFF verification-status", () => {
  it("relays the challenge id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonBackendResponse({ verified: true }, 200)),
    );

    const { GET } =
      await import("../../../../pages/api/auth/verification-status");
    const response = await GET({
      url: new URL("http://test/api/auth/verification-status?challenge_id=abc"),
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ verified: true });
  });
});

describe("BFF confirm-email", () => {
  it("relays the token and returns success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonBackendResponse({ success: true }, 200)),
    );

    const { POST } = await import("../../../../pages/api/auth/confirm-email");
    const response = await POST({
      request: jsonRequest(
        { token: "signed-token" },
        "http://test/api/auth/confirm-email",
      ),
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true });
  });
});

describe("BFF signup", () => {
  it("captures the session cookie and sets the signup toast on 201", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonBackendResponse({ authenticated: true, username: "newuser" }, 201, {
          "Set-Cookie":
            "sessionid=signup-session; HttpOnly; Path=/; SameSite=Lax",
        }),
      ),
    );

    const { POST } = await import("../../../../pages/api/auth/signup");
    const cookies = new FakeCookies();
    const response = await POST({
      request: jsonRequest({
        username: "newuser",
        email: "a@b.com",
        password: "StrongPass1!",
        challenge_id: "abc",
        recaptcha_token: "t",
      }),
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({
      authenticated: true,
      username: "newuser",
    });

    const sessionCookie = cookies.setCalls.find((c) => c.name === "sessionid");
    expect(sessionCookie).toMatchObject({
      value: "signup-session",
      options: { path: "/", httpOnly: true, sameSite: "lax" },
    });

    const toastCookie = cookies.setCalls.find((c) => c.name === "flash_toast");
    expect(toastCookie).toMatchObject({
      value: "signup_success",
      options: { path: "/", maxAge: 5 },
    });
  });
});
