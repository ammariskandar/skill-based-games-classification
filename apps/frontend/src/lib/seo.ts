/**
 * SEO/metadata helpers — SBGC-75.
 *
 * Pure, testable URL and JSON-LD construction. These functions intentionally do
 * not read `import.meta.env` so they run under Node/Vitest; the Astro call
 * sites pass the configured origin in.
 */

export const FALLBACK_SITE_URL = "http://localhost:4321";

/** Normalize and validate the configured public site origin. */
export function resolveSiteOrigin(raw: string | undefined): string {
  const value = (raw ?? "").trim();
  if (!value) {
    return FALLBACK_SITE_URL;
  }

  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error(`PUBLIC_SITE_URL is not a valid URL: ${value}`);
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`PUBLIC_SITE_URL must use http or https: ${value}`);
  }
  if (url.pathname !== "/" && url.pathname !== "") {
    throw new Error(`PUBLIC_SITE_URL must be an origin (no path): ${value}`);
  }
  if (url.search || url.hash) {
    throw new Error(
      `PUBLIC_SITE_URL must not contain a query string or fragment: ${value}`,
    );
  }

  return url.origin;
}

/** Build an absolute canonical URL from an origin and a leading-slash path. */
export function buildCanonicalUrl(origin: string, path: string): string {
  const url = new URL(path, origin);
  url.search = "";
  url.hash = "";
  return url.toString();
}

/** Serialize JSON-LD so user/upstream text cannot break out of a `<script>`. */
export function serializeJsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/[<>&]/g, (ch) => {
    if (ch === "<") return "\\u003c";
    if (ch === ">") return "\\u003e";
    return "\\u0026";
  });
}

export interface VideoGameJsonLdInput {
  name: string;
  url: string;
  description?: string;
  image?: string;
  datePublished?: string;
}

/** Build a `VideoGame` JSON-LD string, omitting unavailable optional fields. */
export function buildVideoGameJsonLd(input: VideoGameJsonLdInput): string {
  const data: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "VideoGame",
    name: input.name,
    url: input.url,
  };
  if (input.description) data.description = input.description;
  if (input.image) data.image = input.image;
  if (input.datePublished) data.datePublished = input.datePublished;
  return serializeJsonLd(data);
}
