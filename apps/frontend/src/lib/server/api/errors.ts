import type { ApiError, ErrorCode } from "./types";

/** Build a normalized ApiError from a machine-readable code. */
export function apiError(
  code: ErrorCode,
  message: string,
  extra?: { status?: number; cause?: unknown },
): ApiError {
  return {
    code,
    message,
    status: extra?.status,
    cause: extra?.cause,
  };
}
