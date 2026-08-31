/**
 * Defensive URL-search-parameter parsing helpers — SBGC-102.
 *
 * Harden the SSR query pipeline against malformed, duplicated, or
 * adversarial query values.  Pure TypeScript over `URLSearchParams` — no
 * Node or DOM APIs beyond the standard global, so the module is safe for
 * both server rendering and client bundles.
 *
 * - Multi-value keys resolve deterministically to the primary scalar
 *   (first submitted value), preserving the codebase's first-wins contract.
 * - Numeric parameters are strictly parsed (digits only) and clamped into
 *   `[min, max]`; garbage, negatives, and floats fall back to the default.
 * - Boolean parameters keep the "true wins" contract used by the
 *   cover-last checkbox form (`true` anywhere beats `false`).
 * - Search strings are stripped of ASCII control characters (`\x00`–`\x1f`,
 *   `\x7f`), trimmed, and bounded in length so over-long or malformed
 *   queries never reach the backend as 422 triggers.
 */

/** ASCII control characters: `\x00`–`\x1f` and `\x7f`. */
// eslint-disable-next-line no-control-regex -- intentional: strips control chars
const CONTROL_CHAR_REGEX = /[\x00-\x1f\x7f]/g;

/**
 * First submitted value for `key`, sanitized: control characters stripped,
 * whitespace trimmed, length capped at `maxLength`.  Returns `undefined`
 * when the key is absent or sanitizes to an empty string.
 */
export function getSafeQueryString(
  searchParams: URLSearchParams,
  key: string,
  maxLength = 100,
): string | undefined {
  const values = searchParams.getAll(key);
  if (values.length === 0) return undefined;
  const cleaned = values[0].replace(CONTROL_CHAR_REGEX, "").trim();
  if (!cleaned) return undefined;
  return cleaned.slice(0, maxLength);
}

/**
 * Strict integer for `key`, clamped into `[min, max]`.
 *
 * Missing, non-numeric, negative, or non-integer values (e.g. `abc`,
 * `-5`, `2.5`) fall back to `defaultValue`; oversized integers (including
 * values beyond `Number.MAX_SAFE_INTEGER` such as `99999999999999999`)
 * clamp to `max`.
 */
export function getSafeQueryInt(
  searchParams: URLSearchParams,
  key: string,
  defaultValue: number,
  min = 1,
  max = 100,
): number {
  const values = searchParams.getAll(key);
  if (values.length === 0) return defaultValue;
  const trimmed = values[0].replace(CONTROL_CHAR_REGEX, "").trim();
  if (!/^[0-9]+$/.test(trimmed)) return defaultValue;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return defaultValue;
  return Math.max(min, Math.min(max, parsed));
}

/**
 * Boolean for `key` preserving the "true wins" contract: an explicit
 * `true`/`1` in any submitted value wins, then `false`/`0`, then the
 * supplied default.  Matching is case-insensitive.
 */
export function getSafeQueryBool(
  searchParams: URLSearchParams,
  key: string,
  defaultValue: boolean,
): boolean {
  const values = searchParams.getAll(key);
  if (values.length === 0) return defaultValue;
  if (values.some((value) => value.toLowerCase() === "true" || value === "1")) {
    return true;
  }
  if (
    values.some((value) => value.toLowerCase() === "false" || value === "0")
  ) {
    return false;
  }
  return defaultValue;
}
