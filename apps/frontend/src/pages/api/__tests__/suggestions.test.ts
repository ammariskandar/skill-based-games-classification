/**
 * Game-suggestion BFF proxy tests — SBGC-240.
 *
 * Exercises `src/pages/api/suggestions.ts` as a plain module with a minimal
 * APIContext stand-in: the route must gate on the session cookie, pre-validate
 * the three fields, forward the session and the edge-resolved client IP to
 * Django, and relay the upstream status (including a 429's `Retry-After`).
 * No real network — `globalThis.fetch` is stubbed.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

class FakeCookies {
  private store = new Map<string, string>();

  get(name: string): { value: string } | undefined {
    const value = this.store.get(name);
    return value === undefined ? undefined : { value };
  }

  set(name: string, value: string): void {
    this.store.set(name, value);
  }

  delete(name: string): void {
    this.store.delete(name);
  }
}

function authenticatedCookies(): FakeCookies {
  const cookies = new FakeCookies();
  cookies.set("sessionid", "test-session-token");
  return cookies;
}

function jsonRequest(
  payload: unknown,
  headers: Record<string, string> = {},
): Request {
  return new Request("http://test/api/suggestions", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
}

function backendResponse(
  body: unknown,
  status: number,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

async function callRoute(
  payload: unknown,
  options: { cookies?: FakeCookies; headers?: Record<string, string> } = {},
) {
  const { POST } = await import("../suggestions");
  return POST({
    request: jsonRequest(payload, options.headers),
    cookies: (options.cookies ?? authenticatedCookies()) as unknown as never,
  } as never);
}

const VALID = {
  name: "Hollow Knight: Silksong",
  storefront_url: "https://store.steampowered.com/app/1030300/",
  remarks: "Please classify this one.",
};

beforeEach(() => {
  vi.stubEnv("DJANGO_API_URL", "http://127.0.0.1:8000");
  vi.resetModules();
});

describe("POST /api/suggestions", () => {
  describe("authentication", () => {
    it("returns 401 without calling Django when no session cookie exists", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const response = await callRoute(VALID, { cookies: new FakeCookies() });

      expect(response.status).toBe(401);
      expect(await response.json()).toEqual({
        error: { code: "UNAUTHENTICATED", message: "Login required." },
      });
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  describe("validation", () => {
    it("returns 400 for a malformed body", async () => {
      vi.stubGlobal("fetch", vi.fn());

      const { POST } = await import("../suggestions");
      const response = await POST({
        request: new Request("http://test/api/suggestions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "not json",
        }),
        cookies: authenticatedCookies() as unknown as never,
      } as never);

      expect(response.status).toBe(400);
    });

    it("returns 422 for a blank name", async () => {
      vi.stubGlobal("fetch", vi.fn());

      const response = await callRoute({ ...VALID, name: "   " });

      expect(response.status).toBe(422);
      const body = (await response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("VALIDATION_ERROR");
    });

    it("returns 422 when the name exceeds 50 characters", async () => {
      vi.stubGlobal("fetch", vi.fn());

      const response = await callRoute({ ...VALID, name: "a".repeat(51) });

      expect(response.status).toBe(422);
    });

    it("returns 422 when the storefront URL exceeds 250 characters", async () => {
      vi.stubGlobal("fetch", vi.fn());

      const response = await callRoute({
        ...VALID,
        storefront_url: `https://example.test/${"a".repeat(250)}`,
      });

      expect(response.status).toBe(422);
    });

    it.each([
      "http://store.steampowered.com/app/1",
      "javascript:alert(1)",
      "data:text/html,hi",
      "//evil.test/app",
      "not-a-url",
    ])(
      "returns 422 for the insecure storefront URL %s",
      async (storefrontUrl) => {
        const fetchMock = vi.fn();
        vi.stubGlobal("fetch", fetchMock);

        const response = await callRoute({
          ...VALID,
          storefront_url: storefrontUrl,
        });

        expect(response.status).toBe(422);
        expect(fetchMock).not.toHaveBeenCalled();
      },
    );

    it("returns 422 when remarks exceed 250 characters", async () => {
      vi.stubGlobal("fetch", vi.fn());

      const response = await callRoute({ ...VALID, remarks: "b".repeat(251) });

      expect(response.status).toBe(422);
    });

    it("accepts an empty storefront URL and empty remarks", async () => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            backendResponse({ success: true, message: "ok" }, 200),
          ),
      );

      const response = await callRoute({
        name: "Silksong",
        storefront_url: "",
        remarks: "",
      });

      expect(response.status).toBe(200);
    });
  });

  describe("dispatch", () => {
    it("relays a valid suggestion with the session and client IP", async () => {
      const fetchMock = vi
        .fn()
        .mockResolvedValue(
          backendResponse({ success: true, message: "ok" }, 200),
        );
      vi.stubGlobal("fetch", fetchMock);

      const response = await callRoute(VALID, {
        headers: { "cf-connecting-ip": "203.0.113.7" },
      });

      expect(response.status).toBe(200);
      expect(await response.json()).toEqual({
        success: true,
        message: "Thanks — your suggestion has been sent.",
      });

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe("http://127.0.0.1:8000/api/v1/suggestions/");
      expect(init.method).toBe("POST");
      const headers = init.headers as Headers;
      expect(headers.get("cookie")).toBe("sessionid=test-session-token");
      expect(headers.get("x-client-real-ip")).toBe("203.0.113.7");
      expect(JSON.parse(init.body as string)).toEqual(VALID);
    });

    it("relays an upstream 422 with its error envelope", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          backendResponse(
            {
              error: {
                code: "VALIDATION_ERROR",
                message: "Storefront URL must be a valid https:// URL.",
                details: [],
              },
            },
            422,
          ),
        ),
      );

      const response = await callRoute(VALID);

      expect(response.status).toBe(422);
      expect(await response.json()).toEqual({
        error: {
          code: "VALIDATION_ERROR",
          message: "Storefront URL must be a valid https:// URL.",
        },
      });
    });

    it("relays an upstream 401 when the session is not valid", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          backendResponse(
            {
              error: {
                code: "AUTHENTICATION_ERROR",
                message: "Authentication required.",
                details: [],
              },
            },
            401,
          ),
        ),
      );

      const response = await callRoute(VALID);

      expect(response.status).toBe(401);
      const body = (await response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("AUTHENTICATION_ERROR");
    });

    it("relays a 429 and its Retry-After window", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          backendResponse(
            {
              error: {
                code: "RATE_LIMITED",
                message:
                  "Please wait 42 seconds before submitting another suggestion.",
                details: [],
              },
            },
            429,
            { "Retry-After": "42" },
          ),
        ),
      );

      const response = await callRoute(VALID);

      expect(response.status).toBe(429);
      expect(response.headers.get("retry-after")).toBe("42");
      const body = (await response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("RATE_LIMITED");
    });

    it("defaults the Retry-After window when the upstream omits it", async () => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            backendResponse({ error: { code: "RATE_LIMITED" } }, 429),
          ),
      );

      const response = await callRoute(VALID);

      expect(response.status).toBe(429);
      expect(response.headers.get("retry-after")).toBe("60");
    });

    it("returns 503 when the upstream is unreachable", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
      );

      const response = await callRoute(VALID);

      expect(response.status).toBe(503);
      const body = (await response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("SERVICE_UNAVAILABLE");
    });
  });
});
