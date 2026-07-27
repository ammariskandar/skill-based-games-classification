/**
 * Server-side Django API client.
 *
 * - Reads DJANGO_API_URL from the environment (server-only).
 * - Accepts relative paths only — no absolute or protocol-relative URLs.
 * - Returns typed ApiResult<T> for every call.
 * - Classifies failures into normalized error categories.
 * - Timeout-safe; caller-cancellable via AbortSignal.
 *
 * IMPORTANT: This module must only be imported from Astro server-side code
 * (frontmatter, API routes, server endpoints).  Do NOT import it into
 * client-side <script> blocks or components that hydrate in the browser.
 */

import { apiError } from "./errors";
import type {
  ApiFailure,
  ApiResult,
  GetOptions,
  PostOptions,
  RequestOptions,
} from "./types";

// ═══ configuration ═══

const API_DEFAULT_TIMEOUT = 8_000; // ms

function getBaseUrl(): string {
  const url = import.meta.env.DJANGO_API_URL;
  if (!url) {
    throw apiError(
      "CONFIG_ERROR",
      "DJANGO_API_URL is not set. Set it in apps/frontend/.env",
    );
  }
  return url.replace(/\/+$/, "");
}

// ═══ path validation ═══

/** Accept only relative API paths.  Reject absolute URLs, protocol-relative
 * URLs, scheme-prefixed URLs, empty strings, and paths without a leading slash. */
function resolveUrl(path: string): string {
  if (!path || path.length === 0) {
    throw apiError("CONFIG_ERROR", "API path must not be empty");
  }
  if (path[0] !== "/") {
    throw apiError("CONFIG_ERROR", `API path must start with /: ${path}`);
  }
  // Protocol-relative: starts with //
  if (path.startsWith("//")) {
    throw apiError("CONFIG_ERROR", "Protocol-relative URLs are not allowed");
  }
  // Absolute: any scheme followed by ://
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(path)) {
    throw apiError(
      "CONFIG_ERROR",
      "Absolute URLs are not allowed for API paths",
    );
  }
  return `${getBaseUrl()}${path}`;
}

// ═══ transport ═══

const JSON_HEADERS: Record<string, string> = { Accept: "application/json" };

async function request<T>(
  method: string,
  path: string,
  body: unknown | undefined,
  opts: RequestOptions,
): Promise<ApiResult<T>> {
  let url: string;
  try {
    url = resolveUrl(path);
  } catch (err: unknown) {
    if (err && typeof err === "object" && "code" in err)
      return { ok: false, error: err as ApiFailure["error"] };
    return { ok: false, error: apiError("CONFIG_ERROR", String(err)) };
  }

  // Return immediately if the caller's signal is already aborted.
  if (opts.signal?.aborted) {
    return { ok: false, error: apiError("ABORTED", "Request was cancelled") };
  }

  const timeoutMs = opts.timeoutMs ?? API_DEFAULT_TIMEOUT;
  const controller = new AbortController();
  let callerAborted = false;

  const timer = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

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

  const headers: Record<string, string> = { ...JSON_HEADERS, ...opts.headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err: unknown) {
    cleanup();
    if (err instanceof DOMException && err.name === "AbortError") {
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

  cleanup();

  if (!response.ok) {
    return {
      ok: false,
      status: response.status,
      error: apiError("HTTP_ERROR", `Server returned ${response.status}`),
    };
  }

  // Handle 204 No Content cleanly
  if (response.status === 204) {
    return { ok: true, data: undefined as unknown as T, status: 204 };
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return {
      ok: false,
      status: response.status,
      error: apiError("INVALID_RESPONSE", "Expected JSON response"),
    };
  }

  let data: T;
  try {
    const text = await response.text();
    if (!text.trim()) {
      return {
        ok: false,
        status: response.status,
        error: apiError("INVALID_RESPONSE", "Empty response body"),
      };
    }
    data = JSON.parse(text) as T;
  } catch (err: unknown) {
    return {
      ok: false,
      status: response.status,
      error: apiError("INVALID_RESPONSE", "Failed to parse response as JSON", {
        cause: err,
      }),
    };
  }

  return { ok: true, data, status: response.status };
}

// ═══ convenience helpers ═══

export async function getJSON<T>(
  path: string,
  opts: GetOptions = {},
): Promise<ApiResult<T>> {
  const { params, ...rest } = opts;
  let resolved = path;
  if (params && Object.keys(params).length > 0) {
    const qs = new URLSearchParams(params).toString();
    resolved = `${path}?${qs}`;
  }
  return request<T>("GET", resolved, undefined, rest);
}

export async function postJSON<T>(
  path: string,
  body: unknown,
  opts: PostOptions = {},
): Promise<ApiResult<T>> {
  const { ...rest } = opts;
  return request<T>("POST", path, body, rest);
}
