/**
 * Server-side Django API client.
 *
 * - Reads DJANGO_API_URL from the environment (server-only).
 * - Accepts relative paths only — no absolute or protocol-relative URLs.
 * - Returns typed ApiResult<T> for every call.
 * - Classifies failures into normalized error categories.
 * - Timeout-safe through body completion; caller-cancellable via AbortSignal.
 * - Explicitly rejects redirects (does not follow 3xx).
 * - Every response body is consumed or cancelled — no GC-dependent cleanup.
 *
 * IMPORTANT: This module must only be imported from Astro server-side code
 * (frontmatter, API routes, server endpoints).  Do NOT import it into
 * client-side <script> blocks or components that hydrate in the browser.
 */

import { apiError, bodySerializationError } from "./errors";
import type { ApiErrorDto } from "../../../types/api";
import type {
  ApiFailure,
  ApiNoContent,
  ApiResult,
  ApiSuccess,
  ErrorCode,
  GetOptions,
  PostOptions,
  RequestOptions,
} from "./types";

// ═══ configuration ═══

const API_DEFAULT_TIMEOUT = 8_000; // ms
const JSON_MEDIA_TYPE = "application/json";
const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

interface ParsedMediaType {
  type: string;
  subtype: string;
}

function parseMediaType(contentType: string | null): ParsedMediaType | null {
  if (!contentType) return null;
  const semi = contentType.indexOf(";");
  const base = semi === -1 ? contentType : contentType.slice(0, semi);
  const [type, subtype] = base.split("/");
  if (!type || !subtype) return null;
  return {
    type: type.trim().toLowerCase(),
    subtype: subtype.trim().toLowerCase(),
  };
}

function isJsonMediaType(ct: string | null): boolean {
  const parsed = parseMediaType(ct);
  if (!parsed) return false;
  if (parsed.type === "application" && parsed.subtype === "json") return true;
  if (parsed.type === "application" && parsed.subtype.endsWith("+json"))
    return true;
  return false;
}

// ═══ URL validation ═══

function validateBaseUrl(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    throw apiError(
      "CONFIG_ERROR",
      "DJANGO_API_URL is not set. Set it in apps/frontend/.env",
    );
  }

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw apiError(
      "CONFIG_ERROR",
      `DJANGO_API_URL is not a valid URL: ${trimmed}`,
    );
  }

  const isLocal = LOCAL_HOSTNAMES.has(parsed.hostname);
  if (parsed.protocol === "http:") {
    if (!isLocal) {
      throw apiError(
        "CONFIG_ERROR",
        `Insecure HTTP protocol is forbidden for remote host: "${parsed.hostname}". HTTPS is required.`,
      );
    }
  } else if (parsed.protocol !== "https:") {
    throw apiError(
      "CONFIG_ERROR",
      `DJANGO_API_URL must use https: (or http: for local development): ${trimmed}`,
    );
  }
  if (parsed.username || parsed.password) {
    throw apiError(
      "CONFIG_ERROR",
      "DJANGO_API_URL must not contain credentials",
    );
  }
  if (parsed.pathname !== "/" && parsed.pathname !== "") {
    throw apiError(
      "CONFIG_ERROR",
      "DJANGO_API_URL must be an origin (no path)",
    );
  }
  if (parsed.search) {
    throw apiError(
      "CONFIG_ERROR",
      "DJANGO_API_URL must not contain a query string",
    );
  }
  if (parsed.hash) {
    throw apiError(
      "CONFIG_ERROR",
      "DJANGO_API_URL must not contain a fragment",
    );
  }

  return parsed.origin;
}

function getBaseUrl(): string {
  const raw = import.meta.env.DJANGO_API_URL;
  return validateBaseUrl(raw ?? "");
}

// ═══ path validation ═══

function resolveUrl(base: string, path: string): string {
  if (!path || path.length === 0) {
    throw apiError("CONFIG_ERROR", "API path must not be empty");
  }
  if (path[0] !== "/") {
    throw apiError("CONFIG_ERROR", `API path must start with /: ${path}`);
  }
  if (path.startsWith("//")) {
    throw apiError("CONFIG_ERROR", "Protocol-relative URLs are not allowed");
  }
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(path)) {
    throw apiError(
      "CONFIG_ERROR",
      "Absolute URLs are not allowed for API paths",
    );
  }
  if (path.includes("#")) {
    throw apiError("CONFIG_ERROR", "API paths must not contain fragments");
  }

  // Reject traversal segments (., .., and percent-encoded equivalents)
  // before URL normalization can erase them.
  const segments = path.split("/");
  for (const seg of segments) {
    let decoded: string;
    try {
      decoded = decodeURIComponent(seg);
    } catch {
      throw apiError(
        "CONFIG_ERROR",
        "API path contains invalid percent encoding",
      );
    }
    if (decoded === "." || decoded === "..") {
      throw apiError(
        "CONFIG_ERROR",
        "API path must not contain traversal segments",
      );
    }
  }

  const resolved = new URL(path, base);
  if (!resolved.href.startsWith(base)) {
    throw apiError(
      "CONFIG_ERROR",
      "API path must not escape the base URL origin",
    );
  }
  return resolved.href;
}

// ═══ timeout validation ═══

function validateTimeout(ms: number | undefined): number {
  const t = ms ?? API_DEFAULT_TIMEOUT;
  if (
    typeof t !== "number" ||
    !Number.isFinite(t) ||
    t <= 0 ||
    !Number.isInteger(t)
  ) {
    throw apiError(
      "CONFIG_ERROR",
      `timeoutMs must be a positive integer (got ${t})`,
    );
  }
  return t;
}

// ═══ helpers ═══

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** Consume and discard a response body to release the connection. */
async function drainBody(response: Response): Promise<void> {
  try {
    await response.text();
  } catch (err) {
    // Surface abort/timeout during draining so the caller can classify it as
    // ABORTED/TIMEOUT instead of silently swallowing the cancellation.  Other
    // drain failures are best-effort connection cleanup and are ignored.
    if (isAbortError(err)) throw err;
  }
}

function isRedirect(status: number): boolean {
  return (
    status === 301 ||
    status === 302 ||
    status === 303 ||
    status === 307 ||
    status === 308
  );
}

/**
 * Status-based fallback error code when the upstream returns no parseable
 * JSON envelope (e.g. a gateway HTML page or a proxy error body).  Mirrors
 * the backend ErrorCode taxonomy for statuses that have canonical codes;
 * everything else stays the generic HTTP_ERROR (SBGC-101).
 */
function fallbackCodeForStatus(status: number): ErrorCode {
  if (status === 404) return "NOT_FOUND";
  if (status === 422) return "VALIDATION_ERROR";
  if (status === 429) return "RATE_LIMITED";
  if (status >= 500) return "SERVICE_UNAVAILABLE";
  return "HTTP_ERROR";
}

// ═══ transport ═══

async function request<T>(
  method: string,
  path: string,
  body: unknown | undefined,
  opts: RequestOptions,
): Promise<ApiResult<T>> {
  // ── 1. validate configuration and build URL ──
  let base: string;
  let url: string;
  try {
    base = getBaseUrl();
    url = resolveUrl(base, path);
  } catch (err: unknown) {
    if (err && typeof err === "object" && "code" in err) {
      return { ok: false, error: err as ApiFailure["error"] };
    }
    return { ok: false, error: apiError("CONFIG_ERROR", String(err)) };
  }

  // ── 2. validate timeout ──
  let timeoutMs: number;
  try {
    timeoutMs = validateTimeout(opts.timeoutMs);
  } catch (err: unknown) {
    if (err && typeof err === "object" && "code" in err) {
      return { ok: false, error: err as ApiFailure["error"] };
    }
    return { ok: false, error: apiError("CONFIG_ERROR", String(err)) };
  }

  // ── 3. pre-aborted caller signal ──
  if (opts.signal?.aborted) {
    return { ok: false, error: apiError("ABORTED", "Request was cancelled") };
  }

  // ── 4. serialize request body (before network catch) ──
  let serializedBody: string | undefined;
  if (body !== undefined) {
    try {
      serializedBody = JSON.stringify(body);
    } catch (err: unknown) {
      return { ok: false, error: bodySerializationError(err) };
    }
  }

  // ── 5. set up cancellation ──
  const controller = new AbortController();
  let callerAborted = false;

  const timer = setTimeout(() => controller.abort(), timeoutMs);

  function onCallerAbort() {
    callerAborted = true;
    controller.abort();
  }

  if (opts.signal) {
    opts.signal.addEventListener("abort", onCallerAbort, { once: true });
  }

  function cleanup() {
    clearTimeout(timer);
    if (opts.signal) {
      opts.signal.removeEventListener("abort", onCallerAbort);
    }
  }

  try {
    // ── 6. build headers ──
    let headers: Headers;
    try {
      headers = new Headers(opts.headers);
    } catch (err: unknown) {
      return {
        ok: false,
        error: apiError(
          "REQUEST_SERIALIZATION",
          err instanceof Error ? err.message : "Invalid headers provided",
          { cause: err },
        ),
      };
    }
    if (!headers.has("Accept")) {
      headers.set("Accept", JSON_MEDIA_TYPE);
    }
    if (serializedBody !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", JSON_MEDIA_TYPE);
    }

    // ── 7. fetch ──
    let response: Response;
    try {
      response = await fetch(url, {
        method,
        headers,
        body: serializedBody ?? null,
        signal: controller.signal,
        redirect: "manual",
      });
    } catch (err: unknown) {
      if (isAbortError(err)) {
        if (callerAborted) {
          return {
            ok: false,
            error: apiError("ABORTED", "Request was cancelled"),
          };
        }
        return {
          ok: false,
          error: apiError("TIMEOUT", `Request timed out after ${timeoutMs}ms`),
        };
      }
      return {
        ok: false,
        error: apiError("NETWORK_ERROR", "Network request failed", {
          cause: err,
        }),
      };
    }

    // ── 8. handle redirects ──
    if (isRedirect(response.status)) {
      await drainBody(response);
      return {
        ok: false,
        status: response.status,
        error: apiError("REDIRECT", `Unexpected redirect (${response.status})`),
      };
    }

    // ── 9. handle non-2xx ──
    if (!response.ok) {
      let apiErrorDto: ApiErrorDto | undefined;
      const contentType = response.headers.get("content-type");

      if (contentType && isJsonMediaType(contentType)) {
        try {
          const text = await response.text();
          const errorJson = JSON.parse(text) as unknown;
          if (
            errorJson &&
            typeof errorJson === "object" &&
            "error" in errorJson &&
            errorJson.error &&
            typeof errorJson.error === "object" &&
            "code" in errorJson.error &&
            "message" in errorJson.error &&
            "details" in errorJson.error &&
            Array.isArray(errorJson.error.details)
          ) {
            apiErrorDto = errorJson.error as ApiErrorDto;
          }
        } catch (err) {
          // Surface abort/timeout during the structured-error read; otherwise
          // fall back to the generic HTTP_ERROR below.
          if (isAbortError(err)) throw err;
        }
      } else {
        await drainBody(response);
      }

      const message =
        apiErrorDto?.message ?? `Server returned ${response.status}`;

      return {
        ok: false,
        status: response.status,
        error: apiError(
          apiErrorDto ? "HTTP_ERROR" : fallbackCodeForStatus(response.status),
          message,
        ),
        apiError: apiErrorDto,
      };
    }

    // ── 10. 204 No Content ──
    if (response.status === 204) {
      await drainBody(response);
      return { ok: true, status: 204 } as ApiNoContent;
    }

    // ── 11. validate media type ──
    const contentType = response.headers.get("content-type");
    if (!isJsonMediaType(contentType)) {
      await drainBody(response);
      return {
        ok: false,
        status: response.status,
        error: apiError("INVALID_RESPONSE", "Expected JSON response"),
      };
    }

    // ── 12. read and parse body (timeout/cancel still active) ──
    let text: string;
    try {
      text = await response.text();
    } catch (err: unknown) {
      if (isAbortError(err)) {
        if (callerAborted) {
          return {
            ok: false,
            error: apiError("ABORTED", "Request was cancelled"),
          };
        }
        return {
          ok: false,
          error: apiError("TIMEOUT", `Request timed out after ${timeoutMs}ms`),
        };
      }
      return {
        ok: false,
        error: apiError("INVALID_RESPONSE", "Failed to read response body", {
          cause: err,
        }),
      };
    }

    if (!text.trim()) {
      return {
        ok: false,
        status: response.status,
        error: apiError("INVALID_RESPONSE", "Empty response body"),
      };
    }

    let data: T;
    try {
      data = JSON.parse(text) as T;
    } catch (err: unknown) {
      return {
        ok: false,
        status: response.status,
        error: apiError(
          "INVALID_RESPONSE",
          "Failed to parse response as JSON",
          {
            cause: err,
          },
        ),
      };
    }

    return { ok: true, data, status: response.status } as ApiSuccess<T>;
  } catch (err: unknown) {
    // Reached when a body drain or structured-error read surfaced an abort, or
    // an unexpected error escaped the guarded branches above.
    if (controller.signal.aborted) {
      if (callerAborted) {
        return {
          ok: false,
          error: apiError("ABORTED", "Request was cancelled", { cause: err }),
        };
      }
      return {
        ok: false,
        error: apiError("TIMEOUT", `Request timed out after ${timeoutMs}ms`, {
          cause: err,
        }),
      };
    }
    return {
      ok: false,
      error: apiError("UNKNOWN_ERROR", "Unexpected transport error", {
        cause: err,
      }),
    };
  } finally {
    cleanup();
  }
}

// ═══ convenience helpers ═══

export async function getJSON<T>(
  path: string,
  opts: GetOptions = {},
): Promise<ApiResult<T>> {
  const { params, ...rest } = opts;
  let resolved = path;
  if (params && Object.keys(params).length > 0) {
    const joiner = path.includes("?") ? "&" : "?";
    resolved = `${path}${joiner}${new URLSearchParams(params).toString()}`;
  }
  return request<T>("GET", resolved, undefined, rest);
}

export async function postJSON<T>(
  path: string,
  body: unknown,
  opts: PostOptions = {},
): Promise<ApiResult<T>> {
  return request<T>("POST", path, body, opts);
}
