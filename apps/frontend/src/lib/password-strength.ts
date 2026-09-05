/**
 * Password strength evaluation — SBGC-218.
 *
 * Pure scoring shared by the PasswordStrengthMeter component and the sign-up
 * page (which gates the submit button on a minimum strength).
 */

export type PasswordTier = "Weak" | "Fair" | "Good" | "Strong";

export interface PasswordStrength {
  /** Number of satisfied criteria: length, lowercase, uppercase, digit, symbol. */
  criteria: number;
  tier: PasswordTier;
  /** Whether the password meets the minimum sign-up requirement. */
  meetsMinimum: boolean;
}

const MIN_LENGTH = 8;

export function evaluatePasswordStrength(password: string): PasswordStrength {
  let criteria = 0;
  if (password.length >= MIN_LENGTH) criteria += 1;
  if (/[a-z]/.test(password)) criteria += 1;
  if (/[A-Z]/.test(password)) criteria += 1;
  if (/[0-9]/.test(password)) criteria += 1;
  if (/[^a-zA-Z0-9]/.test(password)) criteria += 1;

  const tier: PasswordTier =
    criteria <= 1
      ? "Weak"
      : criteria === 2
        ? "Fair"
        : criteria === 3
          ? "Good"
          : "Strong";

  return {
    criteria,
    tier,
    meetsMinimum: criteria >= 3,
  };
}

export function isPasswordStrong(password: string): boolean {
  return evaluatePasswordStrength(password).meetsMinimum;
}
