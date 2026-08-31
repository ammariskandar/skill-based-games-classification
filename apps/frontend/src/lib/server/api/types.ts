import type { ApiErrorDto } from "../../../types/api";

/** Generic typed API result types.  Callers narrow on `result.ok` and
 * `"data" in result` to distinguish success-with-data from no-content. */

/** A successful API response with typed data. */
export interface ApiSuccess<T> {
  ok: true;
  data: T;
  status: number;
}

/** A successful API response with no content (204). */
export interface ApiNoContent {
  ok: true;
  status: 204;
}

/** A failed API response with a normalized error. */
export interface ApiFailure {
  ok: false;
  error: ApiError;
  status?: number;
  /** Structured Django Ninja error envelope, when the upstream returned one. */
  apiError?: ApiErrorDto;
}

/** Discriminated union.  204 responses are `ApiNoContent`. */
export type ApiResult<T> = ApiSuccess<T> | ApiNoContent | ApiFailure;

// ── error taxonomy ──

export type ErrorCode =
  | "CONFIG_ERROR"
  | "REQUEST_SERIALIZATION"
  | "TIMEOUT"
  | "ABORTED"
  | "NETWORK_ERROR"
  | "REDIRECT"
  | "HTTP_ERROR"
  | "NOT_FOUND"
  | "VALIDATION_ERROR"
  | "RATE_LIMITED"
  | "SERVICE_UNAVAILABLE"
  | "INVALID_RESPONSE"
  | "UNKNOWN_ERROR";

export interface ApiError {
  /** Stable machine-readable code for programmatic handling. */
  code: ErrorCode;
  /** Safe human-readable message — never exposes secrets, stack traces, or backend HTML. */
  message: string;
  /** Optional diagnostic context (logging only, never displayed to users).
   *  Never contains raw backend response bodies, HTML, debug output, or credentials. */
  cause?: unknown;
}

// ── request options ──

export interface RequestOptions {
  /** Per-request timeout in ms. Defaults to API_DEFAULT_TIMEOUT.
   *  Must be a positive finite integer. */
  timeoutMs?: number;
  /** AbortSignal for caller-controlled cancellation. */
  signal?: AbortSignal;
  /** Additional headers merged with defaults. */
  headers?: Record<string, string>;
}

export interface GetOptions extends RequestOptions {
  /** Query parameters appended to the URL. */
  params?: Record<string, string>;
}

export type PostOptions = RequestOptions;
