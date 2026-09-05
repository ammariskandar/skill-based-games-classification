/**
 * Account-recovery BFF proxy tests — SBGC-219.
 *
 * Exercises the Astro API route handlers for forgot-username, forgot-password,
 * verify-reset-token, burn-reset-token, and reset-password-confirm as plain
 * modules (invoked with a minimal APIContext stand-in).  No real network —
 * `globalThis.fetch` is stubbed.
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
  url = "http://test/api/auth/forgot-password",
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

const RECOVERY_BODY = {
  email: "bond@example.com",
  recaptcha_token: "test-recaptcha-token",
};

describe("BFF forgot-username", () => {
  it("relays the payload with the client IP header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonBackendResponse(
          { success: true, message: "instructions sent." },
          200,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("../../../../pages/api/auth/forgot-username");
    const response = await POST({
      request: jsonRequest(
        RECOVERY_BODY,
        "http://test/api/auth/forgot-username",
      ),
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      success: true,
      message: "instructions sent.",
    });
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toContain("/api/v1/auth/forgot-username");
    const init = call[1] as RequestInit;
    expect(init.headers).toMatchObject({ "X-Forwarded-For": "127.0.0.1" });
    expect(init.body).toBe(JSON.stringify(RECOVERY_BODY));
  });

  it("forwards the Retry-After header on 429", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonBackendResponse(
          {
            error: { code: "RATE_LIMITED", message: "too fast", details: [] },
          },
          429,
          { "Retry-After": "1800" },
        ),
      ),
    );

    const { POST } = await import("../../../../pages/api/auth/forgot-username");
    const response = await POST({
      request: jsonRequest(
        RECOVERY_BODY,
        "http://test/api/auth/forgot-username",
      ),
    } as never);

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("1800");
  });
});

describe("BFF forgot-password", () => {
  it("relays the dual-match payload with the client IP header", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonBackendResponse(
          { success: true, message: "instructions sent." },
          200,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const payload = {
      username: "bond",
      email: "bond@example.com",
      recaptcha_token: "test-recaptcha-token",
    };
    const { POST } = await import("../../../../pages/api/auth/forgot-password");
    const response = await POST({
      request: jsonRequest(payload, "http://test/api/auth/forgot-password"),
    } as never);

    expect(response.status).toBe(200);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toContain("/api/v1/auth/forgot-password");
    const init = call[1] as RequestInit;
    expect(init.headers).toMatchObject({ "X-Forwarded-For": "127.0.0.1" });
    expect(JSON.parse(String(init.body))).toEqual(payload);
  });
});

describe("BFF verify-reset-token", () => {
  it("relays the signed token and returns the nonce exchange", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonBackendResponse({ valid: true, session_nonce: "nonce-123" }, 200),
        ),
    );

    const { POST } =
      await import("../../../../pages/api/auth/verify-reset-token");
    const response = await POST({
      request: jsonRequest(
        { token: "signed-token" },
        "http://test/api/auth/verify-reset-token",
      ),
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      valid: true,
      session_nonce: "nonce-123",
    });
  });
});

describe("BFF burn-reset-token", () => {
  it("relays a beacon-style JSON payload (sendBeacon Blob)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonBackendResponse({ success: true }, 200));
    vi.stubGlobal("fetch", fetchMock);

    const { POST } =
      await import("../../../../pages/api/auth/burn-reset-token");
    // navigator.sendBeacon bodies arrive as text; build the Request to mimic it.
    const request = new Request("http://test/api/auth/burn-reset-token", {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=UTF-8" },
      body: JSON.stringify({ session_nonce: "nonce-123" }),
    });
    const response = await POST({ request } as never);

    expect(response.status).toBe(200);
    const call = fetchMock.mock.calls[0];
    expect(call[0]).toContain("/api/v1/auth/burn-reset-token");
    const init = call[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      session_nonce: "nonce-123",
    });
  });

  it("answers 200 gracefully when the beacon body is empty", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } =
      await import("../../../../pages/api/auth/burn-reset-token");
    const request = new Request("http://test/api/auth/burn-reset-token", {
      method: "POST",
      body: "",
    });
    const response = await POST({ request } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("BFF reset-password-confirm", () => {
  it("sets the password-reset toast cookie on 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonBackendResponse({ success: true }, 200)),
    );

    const { POST } =
      await import("../../../../pages/api/auth/reset-password-confirm");
    const cookies = new FakeCookies();
    const response = await POST({
      request: jsonRequest(
        {
          session_nonce: "nonce-123",
          new_password: "BrandNewPass9!",
          recaptcha_token: "test-recaptcha-token",
        },
        "http://test/api/auth/reset-password-confirm",
      ),
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ success: true });

    const toastCookie = cookies.setCalls.find((c) => c.name === "flash_toast");
    expect(toastCookie).toMatchObject({
      value: "password_reset_success",
      options: { path: "/", maxAge: 5, httpOnly: false, sameSite: "lax" },
    });

    // No session cookie may be set — a reset never auto-logs-in.
    expect(cookies.setCalls.some((c) => c.name === "sessionid")).toBe(false);
  });

  it("relays backend errors without setting the toast", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonBackendResponse(
          {
            error: {
              code: "EXPIRED_RESET_TOKEN",
              message: "already used",
              details: [],
            },
          },
          400,
        ),
      ),
    );

    const { POST } =
      await import("../../../../pages/api/auth/reset-password-confirm");
    const cookies = new FakeCookies();
    const response = await POST({
      request: jsonRequest(
        {
          session_nonce: "stale",
          new_password: "BrandNewPass9!",
          recaptcha_token: "test-recaptcha-token",
        },
        "http://test/api/auth/reset-password-confirm",
      ),
      cookies: cookies as unknown as never,
    } as never);

    expect(response.status).toBe(400);
    expect(cookies.setCalls.length).toBe(0);
  });
});
