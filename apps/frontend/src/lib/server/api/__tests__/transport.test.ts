/**
 * Behavioural tests for the shared frontend API transport (SBGC-160).
 *
 * Every test mocks globalThis.fetch — no real network requests are made.
 * vitest.config.ts enables restoreMocks + unstubGlobals for clean state.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ApiFailure, ApiNoContent, ApiSuccess } from "../types";

// ═══ helpers ═══

function setEnv(value: string) {
  vi.stubEnv("DJANGO_API_URL", value);
}

/** Stub fetch to return `response` once, then throw if called again. */
function stubFetch(
  response: Response | (() => Response),
): ReturnType<typeof vi.fn> {
  const fn = vi.fn<() => Promise<Response>>();
  if (typeof response === "function") {
    fn.mockImplementation(() => Promise.resolve(response()));
  } else {
    fn.mockResolvedValue(response);
  }
  vi.stubGlobal("fetch", fn);
  return fn;
}

function jsonResponse(
  body: unknown,
  status = 200,
  headers?: Record<string, string>,
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function textResponse(
  body: string,
  status = 200,
  contentType = "text/html",
): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": contentType },
  });
}

function emptyResponse(status: number): Response {
  return new Response(null, { status });
}

async function importClient() {
  // Force re-evaluation so vi.stubEnv takes effect
  vi.resetModules();
  return import("../client");
}

// ═══ tests ═══

describe("API transport", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // ──────────────────────────────────────────────────
  //  CONFIGURATION
  // ──────────────────────────────────────────────────

  describe("configuration validation", () => {
    it("rejects missing DJANGO_API_URL", async () => {
      setEnv("");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects blank DJANGO_API_URL", async () => {
      setEnv("   ");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects relative URL", async () => {
      setEnv("/api");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects unsupported protocol", async () => {
      setEnv("ftp://example.com");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects credentials in URL", async () => {
      setEnv("http://user:pass@127.0.0.1:8000");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects query string in base URL", async () => {
      setEnv("http://127.0.0.1:8000?foo=bar");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects fragment in base URL", async () => {
      setEnv("http://127.0.0.1:8000#section");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects non-root path in base URL", async () => {
      setEnv("http://127.0.0.1:8000/api/v1");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects malformed URL", async () => {
      setEnv("not-a-url");
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("accepts local HTTP origin", async () => {
      setEnv("http://127.0.0.1:8000");
      stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(true);
    });

    it("accepts HTTPS origin", async () => {
      setEnv("https://api.example.com");
      stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(true);
    });

    it("accepts trailing slash on origin", async () => {
      setEnv("http://127.0.0.1:8000/");
      stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(true);
    });

    it("does not call fetch on config error", async () => {
      setEnv("");
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      await getJSON("/api/test");
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  // ──────────────────────────────────────────────────
  //  URL AND PATH HANDLING
  // ──────────────────────────────────────────────────

  describe("URL and path handling", () => {
    beforeEach(() => {
      setEnv("http://127.0.0.1:8000");
    });

    it("constructs URL from base + path", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      await getJSON("/api/games");
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toBe("http://127.0.0.1:8000/api/games");
    });

    it("rejects empty path", async () => {
      const { getJSON } = await importClient();
      const r = await getJSON("");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects path without leading slash", async () => {
      const { getJSON } = await importClient();
      const r = await getJSON("api/games");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects protocol-relative path", async () => {
      const { getJSON } = await importClient();
      const r = await getJSON("//evil.com/api");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects absolute URL path", async () => {
      const { getJSON } = await importClient();
      const r = await getJSON("http://evil.com/api");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("rejects fragment in path", async () => {
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test#section");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("accepts dot-segments (URL constructor normalises)", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      const r = await getJSON("/../etc/passwd");
      // URL constructor normalises /../etc/passwd to /etc/passwd
      expect(r.ok).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("appends query parameters", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      await getJSON("/api/search", { params: { q: "test" } });
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain("?q=test");
      expect(calledUrl).toContain("http://127.0.0.1:8000/api/search");
    });

    it("handles existing query in path with & joiner", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      await getJSON("/api/search?sort=asc", { params: { q: "test" } });
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain("sort=asc");
      expect(calledUrl).toContain("q=test");
      expect(calledUrl).toContain("&");
    });
  });

  // ──────────────────────────────────────────────────
  //  REDIRECT REJECTION
  // ──────────────────────────────────────────────────

  describe("redirect rejection", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    for (const status of [301, 302, 303, 307, 308]) {
      it(`rejects ${status} redirect`, async () => {
        stubFetch(emptyResponse(status));
        const { getJSON } = await importClient();
        const r = await getJSON("/api/redirect");
        expect(r.ok).toBe(false);
        const f = r as ApiFailure;
        expect(f.error.code).toBe("REDIRECT");
        expect(f.status).toBe(status);
      });

      it(`does not follow ${status} redirect (manual mode)`, async () => {
        const fetchMock = stubFetch(emptyResponse(status));
        const { getJSON } = await importClient();
        await getJSON("/api/redirect");
        // fetch called once, no second call
        expect(fetchMock).toHaveBeenCalledTimes(1);
      });
    }
  });

  // ──────────────────────────────────────────────────
  //  REQUEST SERIALIZATION
  // ──────────────────────────────────────────────────

  describe("request serialization", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("serializes valid JSON body", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { postJSON } = await importClient();
      await postJSON("/api/submit", { name: "test" });
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const init = fetchMock.mock.calls[0][1] as RequestInit;
      expect(init.body).toBe('{"name":"test"}');
    });

    it("rejects cyclic value with REQUEST_SERIALIZATION", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const { postJSON } = await importClient();
      const obj: Record<string, unknown> = {};
      obj.self = obj;
      const r = await postJSON("/api/submit", obj);
      expect(r.ok).toBe(false);
      const f = r as ApiFailure;
      expect(f.error.code).toBe("REQUEST_SERIALIZATION");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rejects BigInt with REQUEST_SERIALIZATION", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const { postJSON } = await importClient();
      const r = await postJSON("/api/submit", BigInt(1));
      expect(r.ok).toBe(false);
      const f = r as ApiFailure;
      expect(f.error.code).toBe("REQUEST_SERIALIZATION");
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });

  // ──────────────────────────────────────────────────
  //  HEADERS
  // ──────────────────────────────────────────────────

  describe("headers", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("sets default Accept: application/json", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      await getJSON("/api/test");
      const init = fetchMock.mock.calls[0][1] as RequestInit;
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get("Accept")).toBe("application/json");
    });

    it("allows caller to override Accept", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      await getJSON("/api/test", { headers: { Accept: "text/plain" } });
      const init = fetchMock.mock.calls[0][1] as RequestInit;
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get("Accept")).toBe("text/plain");
    });

    it("sets Content-Type for POST with body", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { postJSON } = await importClient();
      await postJSON("/api/submit", { x: 1 });
      const init = fetchMock.mock.calls[0][1] as RequestInit;
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get("Content-Type")).toBe("application/json");
    });

    it("does not set Content-Type for bodyless GET", async () => {
      const fetchMock = stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      await getJSON("/api/test");
      const init = fetchMock.mock.calls[0][1] as RequestInit;
      const headers = new Headers(init.headers as HeadersInit);
      expect(headers.get("Content-Type")).toBeNull();
    });
  });

  // ──────────────────────────────────────────────────
  //  SUCCESSFUL RESPONSES
  // ──────────────────────────────────────────────────

  describe("successful responses", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("parses application/json", async () => {
      stubFetch(jsonResponse({ items: [1, 2, 3] }));
      const { getJSON } = await importClient();
      const r = await getJSON<{ items: number[] }>("/api/test");
      expect(r.ok).toBe(true);
      const s = r as ApiSuccess<{ items: number[] }>;
      expect(s.data.items).toEqual([1, 2, 3]);
      expect(s.status).toBe(200);
    });

    it("parses application/json with charset", async () => {
      stubFetch(
        new Response('{"ok":true}', {
          status: 200,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        }),
      );
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(true);
    });

    it("parses application/*+json", async () => {
      stubFetch(
        new Response('{"ok":true}', {
          status: 200,
          headers: { "Content-Type": "application/vnd.api+json" },
        }),
      );
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(true);
    });
  });

  // ──────────────────────────────────────────────────
  //  204 NO CONTENT
  // ──────────────────────────────────────────────────

  describe("204 No Content", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("returns ApiNoContent with ok:true and no data", async () => {
      stubFetch(emptyResponse(204));
      const { getJSON } = await importClient();
      const r = await getJSON<unknown>("/api/test");
      expect(r.ok).toBe(true);
      expect("data" in r).toBe(false);
      expect((r as ApiNoContent).status).toBe(204);
    });
  });

  // ──────────────────────────────────────────────────
  //  NON-SUCCESS RESPONSES
  // ──────────────────────────────────────────────────

  describe("non-success responses", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    for (const status of [400, 401, 403, 404, 429, 500, 503]) {
      it(`handles ${status} as HTTP_ERROR`, async () => {
        stubFetch(textResponse("error", status));
        const { getJSON } = await importClient();
        const r = await getJSON("/api/test");
        expect(r.ok).toBe(false);
        const f = r as ApiFailure;
        expect(f.error.code).toBe("HTTP_ERROR");
        expect(f.status).toBe(status);
      });
    }
  });

  // ──────────────────────────────────────────────────
  //  MEDIA TYPE HANDLING
  // ──────────────────────────────────────────────────

  describe("media type handling", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("rejects text/html as INVALID_RESPONSE", async () => {
      stubFetch(textResponse("<html></html>", 200));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("INVALID_RESPONSE");
    });

    it("rejects plain text as INVALID_RESPONSE", async () => {
      stubFetch(textResponse("hello", 200, "text/plain"));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("INVALID_RESPONSE");
    });

    it("rejects missing Content-Type as INVALID_RESPONSE", async () => {
      stubFetch(new Response('{"ok":true}', { status: 200 }));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("INVALID_RESPONSE");
    });
  });

  // ──────────────────────────────────────────────────
  //  MALFORMED JSON
  // ──────────────────────────────────────────────────

  describe("malformed JSON", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("returns INVALID_RESPONSE for unparseable JSON", async () => {
      stubFetch(
        new Response("not json", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test");
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("INVALID_RESPONSE");
    });
  });

  // ──────────────────────────────────────────────────
  //  TIMEOUT
  // ──────────────────────────────────────────────────

  describe("timeout", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("returns TIMEOUT when fetch does not resolve", async () => {
      const fetchMock = vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_, reject) => {
            const signal = init?.signal as AbortSignal | undefined;
            if (signal) {
              signal.addEventListener(
                "abort",
                () => reject(new DOMException("Aborted", "AbortError")),
                { once: true },
              );
            }
          }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test", { timeoutMs: 1 });
      expect(r.ok).toBe(false);
      const f = r as ApiFailure;
      expect(f.error.code).toBe("TIMEOUT");
    });

    it("rejects invalid timeout value", async () => {
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test", { timeoutMs: -1 });
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("CONFIG_ERROR");
    });

    it("succeeds when fetch resolves before timeout", async () => {
      stubFetch(jsonResponse({ ok: true }));
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test", { timeoutMs: 5000 });
      expect(r.ok).toBe(true);
    });
  });

  // ──────────────────────────────────────────────────
  //  CALLER CANCELLATION
  // ──────────────────────────────────────────────────

  describe("caller cancellation", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("returns ABORTED for pre-aborted signal", async () => {
      const controller = new AbortController();
      controller.abort();
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      const r = await getJSON("/api/test", { signal: controller.signal });
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("ABORTED");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("returns ABORTED when caller aborts during fetch", async () => {
      const controller = new AbortController();
      const fetchMock = vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_, reject) => {
            const signal = init?.signal as AbortSignal | undefined;
            if (signal) {
              signal.addEventListener(
                "abort",
                () => reject(new DOMException("Aborted", "AbortError")),
                { once: true },
              );
            }
          }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      const promise = getJSON("/api/test", {
        signal: controller.signal,
        timeoutMs: 1000,
      });
      controller.abort();
      const r = await promise;
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("ABORTED");
    });

    it("distinguishes caller abort from timeout", async () => {
      const controller = new AbortController();
      const fetchMock = vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_, reject) => {
            const signal = init?.signal as AbortSignal | undefined;
            if (signal) {
              signal.addEventListener(
                "abort",
                () => reject(new DOMException("Aborted", "AbortError")),
                { once: true },
              );
            }
          }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      const promise = getJSON("/api/test", {
        signal: controller.signal,
        timeoutMs: 1000,
      });
      controller.abort();
      const r = await promise;
      expect(r.ok).toBe(false);
      expect((r as ApiFailure).error.code).toBe("ABORTED");
    });
  });

  // ──────────────────────────────────────────────────
  //  NO-RETRY GUARANTEE
  // ──────────────────────────────────────────────────

  describe("no-retry guarantee", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("calls fetch only once on network failure", async () => {
      const fetchMock = vi.fn().mockRejectedValue(new Error("Connection lost"));
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      await getJSON("/api/test");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("calls fetch only once on timeout", async () => {
      const fetchMock = vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise<Response>((_, reject) => {
            const signal = init?.signal as AbortSignal | undefined;
            if (signal) {
              signal.addEventListener(
                "abort",
                () => reject(new DOMException("Aborted", "AbortError")),
                { once: true },
              );
            }
          }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const { getJSON } = await importClient();
      await getJSON("/api/test", { timeoutMs: 1 });
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    for (const status of [301, 302, 303, 307, 308, 429, 503]) {
      it(`calls fetch only once on ${status}`, async () => {
        const fetchMock = stubFetch(emptyResponse(status));
        const { getJSON } = await importClient();
        await getJSON("/api/test");
        expect(fetchMock).toHaveBeenCalledTimes(1);
      });
    }
  });

  // ──────────────────────────────────────────────────
  //  postJSON
  // ──────────────────────────────────────────────────

  describe("postJSON", () => {
    beforeEach(() => setEnv("http://127.0.0.1:8000"));

    it("sends POST with JSON body", async () => {
      const fetchMock = stubFetch(jsonResponse({ created: true }, 201));
      const { postJSON } = await importClient();
      const r = await postJSON<{ created: boolean }>("/api/create", {
        name: "test",
      });
      expect(r.ok).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const init = fetchMock.mock.calls[0][1] as RequestInit;
      expect(init.method).toBe("POST");
      expect(init.body).toBe('{"name":"test"}');
    });
  });
});
