/**
 * SEO/metadata helper tests — SBGC-75.
 */

import { describe, expect, it } from "vitest";

import {
  buildCanonicalUrl,
  buildVideoGameJsonLd,
  FALLBACK_SITE_URL,
  resolveSiteOrigin,
  serializeJsonLd,
} from "./seo";

describe("resolveSiteOrigin", () => {
  it("falls back to the localhost default when unset or blank", () => {
    expect(resolveSiteOrigin(undefined)).toBe(FALLBACK_SITE_URL);
    expect(resolveSiteOrigin("")).toBe(FALLBACK_SITE_URL);
    expect(resolveSiteOrigin("   ")).toBe(FALLBACK_SITE_URL);
  });

  it("normalizes a valid origin and strips a trailing slash", () => {
    expect(resolveSiteOrigin("https://example.com")).toBe(
      "https://example.com",
    );
    expect(resolveSiteOrigin("https://example.com/")).toBe(
      "https://example.com",
    );
    expect(resolveSiteOrigin("http://localhost:4321")).toBe(
      "http://localhost:4321",
    );
  });

  it("rejects a malformed URL", () => {
    expect(() => resolveSiteOrigin("not a url")).toThrow(/not a valid URL/);
  });

  it("rejects a non-http(s) protocol", () => {
    expect(() => resolveSiteOrigin("ftp://example.com")).toThrow(
      /http or https/,
    );
  });

  it("rejects a path, query string, or fragment", () => {
    expect(() => resolveSiteOrigin("https://example.com/base")).toThrow(
      /origin/,
    );
    expect(() => resolveSiteOrigin("https://example.com?x=1")).toThrow(/query/);
    expect(() => resolveSiteOrigin("https://example.com#frag")).toThrow(
      /fragment/,
    );
  });
});

describe("buildCanonicalUrl", () => {
  it("builds an absolute URL from an origin and path", () => {
    expect(buildCanonicalUrl("https://example.com", "/games/portal-2")).toBe(
      "https://example.com/games/portal-2",
    );
  });

  it("does not double the slash when the origin has a trailing slash", () => {
    expect(buildCanonicalUrl("https://example.com/", "/games/portal-2")).toBe(
      "https://example.com/games/portal-2",
    );
  });

  it("strips a query string and fragment from the path", () => {
    expect(
      buildCanonicalUrl("https://example.com", "/games/portal-2?x=1#top"),
    ).toBe("https://example.com/games/portal-2");
  });
});

describe("serializeJsonLd", () => {
  it("escapes characters that could break out of a script tag", () => {
    const out = serializeJsonLd({
      name: "</script><script>alert(1)</script>",
    });
    expect(out).not.toContain("</script>");
    expect(out).toContain("\\u003c");
  });
});

describe("buildVideoGameJsonLd", () => {
  it("includes name, url, and all available optional fields", () => {
    const jsonLd = buildVideoGameJsonLd({
      name: "Portal 2",
      url: "https://example.com/games/portal-2",
      description: "A puzzle game.",
      image: "https://example.com/header.jpg",
      datePublished: "2011-04-19",
    });
    expect(JSON.parse(jsonLd)).toEqual({
      "@context": "https://schema.org",
      "@type": "VideoGame",
      name: "Portal 2",
      url: "https://example.com/games/portal-2",
      description: "A puzzle game.",
      image: "https://example.com/header.jpg",
      datePublished: "2011-04-19",
    });
  });

  it("omits unavailable optional fields", () => {
    const jsonLd = buildVideoGameJsonLd({
      name: "Chess",
      url: "https://example.com/games/chess",
    });
    expect(JSON.parse(jsonLd)).toEqual({
      "@context": "https://schema.org",
      "@type": "VideoGame",
      name: "Chess",
      url: "https://example.com/games/chess",
    });
  });

  it("never includes rating or classification data", () => {
    const jsonLd = buildVideoGameJsonLd({
      name: "Portal 2",
      url: "https://example.com/games/portal-2",
      description: "A puzzle game.",
      image: "https://example.com/header.jpg",
      datePublished: "2011-04-19",
    });
    expect(jsonLd).not.toContain("rating");
    expect(jsonLd).not.toContain("review");
    expect(jsonLd).not.toContain("confidence");
    expect(jsonLd).not.toContain("challenge");
    expect(jsonLd).not.toContain("reward");
  });
});
