/**
 * Auth BFF proxy tests — SBGC-217.
 *
 * Exercises the Astro API route handlers in `src/pages/api/auth/` as plain
 * modules (invoked with a minimal APIContext stand-in), asserting that the
 * BFF relays the Django session cookie, sets the 5-second flash toast,
 * forwards error statuses/headers, and clears the local session on logout.
 * No real network — `globalThis.fetch` is stubbed.
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
  readonly deleteCalls: Array<{
    name: string;
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

  delete(name: string, options?: Record<string, unknown>): void {
    this.store.delete(name);
    this.deleteCalls.push({ name, options });
  }
}

function jsonRequest(payload: unknown): Request {
  return new Request("http://test/api/auth/login", {
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

describe("BFF login", () => {
  it("relays the session cookie and sets the 5s toast cookie", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonBackendResponse({ authenticated: true, username: "ammaris" }, 200, {
          "Set-Cookie":
            "sessionid=test-session-token; HttpOnly; Path=/; SameSite=Lax",
        }),
      ),
    );

    const { POST } = await import("../../../../pages/api/auth/login");
    const cookies = new FakeCookies();
    const response = await POST({
      request: jsonRequest({ username: "ammaris", password: "secret" }),
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      authenticated: true,
      username: "ammaris",
    });

    const sessionCookie = cookies.setCalls.find((c) => c.name === "sessionid");
    expect(sessionCookie).toMatchObject({
      value: "test-session-token",
      options: { path: "/", httpOnly: true, sameSite: "lax" },
    });

    const toastCookie = cookies.setCalls.find((c) => c.name === "flash_toast");
    expect(toastCookie).toMatchObject({
      value: "login_success",
      options: { path: "/", maxAge: 5, httpOnly: false, sameSite: "lax" },
    });
  });

  it("propagates a 401 error body unchanged", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonBackendResponse(
          {
            error: {
              code: "AUTHENTICATION_ERROR",
              message: "Invalid username or password.",
              details: [],
            },
          },
          401,
        ),
      ),
    );

    const { POST } = await import("../../../../pages/api/auth/login");
    const cookies = new FakeCookies();
    const response = await POST({
      request: jsonRequest({ username: "ammaris", password: "wrong" }),
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe("AUTHENTICATION_ERROR");
    expect(cookies.setCalls).toHaveLength(0);
  });

  it("propagates a 429 error and forwards Retry-After", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonBackendResponse(
          {
            error: {
              code: "RATE_LIMITED",
              message: "Too many failed login attempts.",
              details: [],
            },
          },
          429,
          { "Retry-After": "60" },
        ),
      ),
    );

    const { POST } = await import("../../../../pages/api/auth/login");
    const cookies = new FakeCookies();
    const response = await POST({
      request: jsonRequest({ username: "ammaris", password: "wrong" }),
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(429);
    expect(response.headers.get("Retry-After")).toBe("60");
    expect((await response.json()).error.code).toBe("RATE_LIMITED");
    expect(cookies.setCalls).toHaveLength(0);
  });
});

describe("BFF logout", () => {
  it("deletes the session cookie, sets the toast, and redirects home", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 200 })),
    );

    const { POST } = await import("../../../../pages/api/auth/logout");
    const cookies = new FakeCookies();
    cookies.set("sessionid", "existing-session", { path: "/" });

    const redirect = vi.fn(
      (path: string, status?: number) =>
        new Response(null, {
          status: status ?? 302,
          headers: { Location: path },
        }),
    );

    const response = await POST({
      cookies: cookies as unknown as never,
      redirect: redirect as never,
    } as never);

    expect(redirect).toHaveBeenCalledWith("/", 303);
    expect(response.status).toBe(303);
    expect(cookies.deleteCalls).toContainEqual({
      name: "sessionid",
      options: { path: "/" },
    });
    expect(cookies.setCalls).toContainEqual(
      expect.objectContaining({
        name: "flash_toast",
        value: "logout_success",
        options: expect.objectContaining({ maxAge: 5 }),
      }),
    );
  });
});

describe("BFF status", () => {
  it("returns unauthenticated when no session cookie is present", async () => {
    const { GET } = await import("../../../../pages/api/auth/status");
    const response = await GET({
      cookies: new FakeCookies() as unknown as never,
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      authenticated: false,
      username: null,
    });
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns the authenticated username from a valid session", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonBackendResponse(
            { authenticated: true, username: "ammaris" },
            200,
          ),
        ),
    );

    const { GET } = await import("../../../../pages/api/auth/status");
    const cookies = new FakeCookies();
    cookies.set("sessionid", "valid-session", { path: "/" });

    const response = await GET({
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      authenticated: true,
      username: "ammaris",
    });
  });
});
