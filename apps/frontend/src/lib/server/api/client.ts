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

function resolveUrl(path: string): string {
  if (!path.startsWith("/")) {
    throw apiError(
      "CONFIG_ERROR",
      `API path must be relative (start with /): ${path}`,
    );
  }
  if (/^https?:/i.test(path)) {
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

  const timeoutMs = opts.timeoutMs ?? API_DEFAULT_TIMEOUT;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // Merge external signal with timeout
  if (opts.signal) {
    opts.signal.addEventListener("abort", () => controller.abort(), {
      once: true,
    });
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
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      if (opts.signal?.aborted) {
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
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    const preview = text.slice(0, 200);
    return {
      ok: false,
      status: response.status,
      error: apiError("HTTP_ERROR", `Server returned ${response.status}`, {
        status: response.status,
        cause: preview || undefined,
      }),
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
