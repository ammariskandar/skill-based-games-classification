/**
 * End-to-end failure-path tests for the server API adapters (SBGC-92).
 *
 * Unlike the mocked-`fetch` transport tests, these run the real Node fetch
 * against a local `http.createServer` (or a deliberately closed port) so the
 * adapter + transport stack is exercised across the actual network boundary.
 * Every scenario verifies truthful error classification and that surfaced
 * messages never leak raw network internals or stack traces.
 */

import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
// The frontend intentionally has no `@types/node` (its globals would collide
// with the DOM lib across the Astro client/server boundary); the tiny
// `node:http` surface this harness touches is typed locally below.
// @ts-expect-error — no @types/node in this project
import { createServer } from "node:http";

type MockRequest = { url?: string };
type MockResponse = {
  setHeader(name: string, value: string): void;
  writeHead(status: number): void;
  end(chunk?: string): void;
};
type MockServer = {
  listen(port: number, host: string, callback: () => void): void;
  close(callback: (error?: Error) => void): void;
  address(): { port: number } | string | null;
};

function setEnv(value: string) {
  vi.stubEnv("DJANGO_API_URL", value);
}

async function importGames() {
  vi.resetModules();
  return import("../games");
}

/** Any message surfaced to a user must never contain these internals. */
const FORBIDDEN_SUBSTRINGS = [
  "stack",
  "node_modules",
  "ECONNREFUSED",
  "ENOTFOUND",
  "fetch failed",
  "TypeError",
  "at ",
];

function expectSanitized(...messages: Array<string | undefined>): void {
  for (const message of messages) {
    for (const forbidden of FORBIDDEN_SUBSTRINGS) {
      expect(message ?? "").not.toContain(forbidden);
    }
  }
}

let server: MockServer;
let baseUrl: string;

beforeAll(async () => {
  server = createServer((req: MockRequest, res: MockResponse) => {
    const url = req.url ?? "";
    if (url.includes("html-502")) {
      res.setHeader("Content-Type", "text/html");
      res.writeHead(502);
      res.end("<html><body>502 Bad Gateway</body></html>");
      return;
    }
    // Default: a structured Django Ninja 500 JSON error envelope.
    res.setHeader("Content-Type", "application/json");
    res.writeHead(500);
    res.end(
      JSON.stringify({
        error: {
          code: "SERVER_ERROR",
          message: "Database timeout",
          details: [],
        },
      }),
    );
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("mock server failed to bind");
  }
  baseUrl = `http://127.0.0.1:${address.port}`;
});

afterAll(async () => {
  await new Promise<void>((resolve, reject) =>
    server.close((err) => (err ? reject(err) : resolve())),
  );
});

/** Reserve an ephemeral port and release it so nothing listens there. */
async function unusedPort(): Promise<number> {
  const temp: MockServer = createServer();
  await new Promise<void>((resolve) => temp.listen(0, "127.0.0.1", resolve));
  const address = temp.address();
  const port = address && typeof address === "object" ? address.port : 0;
  await new Promise<void>((resolve) => temp.close(() => resolve()));
  return port;
}

describe("upstream failure paths (real network)", () => {
  it("classifies a 500 JSON error envelope as HTTP_ERROR with apiError", async () => {
    setEnv(baseUrl);
    const { getGameDetail } = await importGames();

    await expect(getGameDetail("json-500")).rejects.toMatchObject({
      name: "BackendApiError",
      failure: {
        status: 500,
        error: { code: "HTTP_ERROR", message: "Database timeout" },
        apiError: {
          code: "SERVER_ERROR",
          message: "Database timeout",
          details: [],
        },
      },
    });
  });

  it("degrades a 502 HTML gateway page without JSON parsing errors", async () => {
    setEnv(baseUrl);
    const { BackendApiError, getGameDetail } = await importGames();

    const error = await getGameDetail("html-502").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(BackendApiError);
    const backendError = error as {
      message: string;
      failure?: {
        status?: number;
        error?: { code?: string; message?: string };
        apiError?: unknown;
      };
    };
    expect(backendError.failure?.status).toBe(502);
    expect(backendError.failure?.error?.code).toBe("HTTP_ERROR");
    expect(backendError.failure?.error?.message).toBe("Server returned 502");
    expect(backendError.failure?.apiError).toBeUndefined();
  });

  it("classifies a connection refusal as NETWORK_ERROR with a sanitized message", async () => {
    setEnv(`http://127.0.0.1:${await unusedPort()}`);
    const { BackendApiError, getGameDetail } = await importGames();

    const error = await getGameDetail("anything").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(BackendApiError);
    const backendError = error as {
      message: string;
      failure?: { error?: { code?: string; message?: string } };
    };
    expect(backendError.failure?.error?.code).toBe("NETWORK_ERROR");
    expectSanitized(backendError.message, backendError.failure?.error?.message);
  });

  it("never surfaces stack traces or raw network internals in any failure message", async () => {
    setEnv(baseUrl);
    const { getGameDetail, getGameSearchIndex } = await importGames();

    const errors: Array<{ message: string; failureMessage?: string }> = [];
    for (const attempt of [
      () => getGameDetail("json-500"),
      () => getGameDetail("html-502"),
      () => getGameSearchIndex(),
    ]) {
      try {
        await attempt();
      } catch (err: unknown) {
        const e = err as {
          message: string;
          failure?: { error?: { message?: string } };
        };
        errors.push({
          message: e.message,
          failureMessage: e.failure?.error?.message,
        });
      }
    }

    expect(errors.length).toBeGreaterThan(0);
    for (const { message, failureMessage } of errors) {
      expectSanitized(message, failureMessage);
    }
  });
});
