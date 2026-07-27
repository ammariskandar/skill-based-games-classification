/** Generic typed API result type.  Distinguishes success from failure so
 * callers never have to check HTTP status manually. */

/** A successful API response with typed data. */
export interface ApiSuccess<T> {
  ok: true;
  data: T;
  status: number;
}

/** A failed API response with a normalized error. */
export interface ApiFailure {
  ok: false;
  error: ApiError;
  status?: number;
}

/** Discriminated union — callers narrow on `result.ok`. */
export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

// ── error types ──

export type ErrorCode =
  | "CONFIG_ERROR"
  | "TIMEOUT"
  | "ABORTED"
  | "NETWORK_ERROR"
  | "HTTP_ERROR"
  | "INVALID_RESPONSE"
  | "UNKNOWN_ERROR";

export interface ApiError {
  /** Stable machine-readable code for programmatic handling. */
  code: ErrorCode;
  /** Safe human-readable message — never exposes secrets or stack traces. */
  message: string;
  /** HTTP status when the server responded. */
  status?: number;
  /** Optional diagnostic context (safe for logging, never for display). */
  cause?: unknown;
}

// ── request options ──

export interface RequestOptions {
  /** Per-request timeout in ms. Defaults to API_DEFAULT_TIMEOUT. */
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

export interface PostOptions extends RequestOptions {
  /** JSON-serializable body. */
  body?: unknown;
}
