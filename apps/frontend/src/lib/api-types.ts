/**
 * Backwards-compatible barrel for the shared API contract (SBGC-89).
 *
 * New code should import from `../types/api`; this module keeps the shorter
 * `lib/api-types` path working for existing callers.
 */
export * from "../types/api";
