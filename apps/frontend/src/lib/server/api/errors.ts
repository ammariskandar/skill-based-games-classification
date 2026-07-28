import type { ApiError, ErrorCode } from "./types";

/** Build a normalized ApiError from a machine-readable code. */
export function apiError(
  code: ErrorCode,
  message: string,
  extra?: { cause?: unknown },
): ApiError {
  return {
    code,
    message,
    cause: extra?.cause,
  };
}

/** The caller's body argument cannot be serialised to JSON. */
export function bodySerializationError(cause: unknown): ApiError {
  return apiError("REQUEST_SERIALIZATION", "Failed to serialize request body", {
    cause,
  });
}
