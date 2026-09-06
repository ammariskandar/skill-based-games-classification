import { describe, expect, it } from "vitest";

import {
  stripServerIdentificationHeaders,
  FORBIDDEN_BANNER_HEADERS,
} from "./banner-headers";

describe("stripServerIdentificationHeaders", () => {
  it("removes Server and X-Powered-By from outgoing responses", () => {
    const headers = new Headers({
      Server: "gunicorn/21.2.0",
      "X-Powered-By": "Express",
      "Content-Type": "application/json",
    });
    stripServerIdentificationHeaders(headers);
    expect(headers.has("server")).toBe(false);
    expect(headers.has("x-powered-by")).toBe(false);
    // Unrelated headers are preserved untouched.
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("matches header names case-insensitively", () => {
    const headers = new Headers({
      server: "gunicorn/21.2.0",
      "X-POWERED-BY": "Astro",
    });
    stripServerIdentificationHeaders(headers);
    expect(headers.has("Server")).toBe(false);
    expect(headers.has("X-Powered-By")).toBe(false);
  });

  it("is a no-op when no banner headers are present", () => {
    const headers = new Headers({ "Content-Type": "text/html" });
    stripServerIdentificationHeaders(headers);
    expect([...headers.keys()]).toEqual(["content-type"]);
  });

  it("targets exactly the two banner headers", () => {
    expect([...FORBIDDEN_BANNER_HEADERS].sort()).toEqual([
      "server",
      "x-powered-by",
    ]);
  });
});
