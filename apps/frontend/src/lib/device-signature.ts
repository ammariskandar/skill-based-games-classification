/**
 * Device signature capture — SBGC-218 dropoff-resume gate.
 *
 * A coarse, stable identity for "the exact system that requested a
 * verification challenge": OS family, browser family, and IANA timezone.
 * Used to ensure a previously-verified challenge is only resumed from the
 * same system that created it (no cross-device dropoff resume).
 *
 * This is an anti-abuse *aid*, not an authentication boundary: every field is
 * client-asserted and trivially spoofable.  The authoritative gate remains the
 * server's VERIFIED challenge check — the signature only decides whether the
 * sign-up page may silently reuse a stored challenge instead of sending a new
 * verification email.
 */

export interface DeviceSignature {
  os: string;
  browser: string;
  timezone: string;
}

export function detectOs(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes("android")) return "android";
  if (/(iphone|ipad|ipod)/.test(ua)) return "ios";
  if (ua.includes("windows")) return "windows";
  if (ua.includes("mac os x") || ua.includes("macintosh")) return "macos";
  if (ua.includes("cros")) return "chromeos";
  if (ua.includes("linux")) return "linux";
  return "unknown";
}

export function detectBrowser(userAgent: string): string {
  const ua = userAgent.toLowerCase();
  if (ua.includes("edg/")) return "edge";
  if (ua.includes("opr/") || ua.includes("opera")) return "opera";
  if (ua.includes("firefox/")) return "firefox";
  if (ua.includes("chrome/") || ua.includes("chromium/")) return "chrome";
  if (ua.includes("safari/")) return "safari";
  return "unknown";
}

export function detectTimezone(
  ianaName: string | undefined,
  offsetMinutes: number,
): string {
  if (ianaName) return ianaName;
  // Fallback when the IANA name is unavailable: an east-positive minute offset
  // (UTC+8 → "utc+480") is stable enough for a same-system signature.
  const eastPositive = -Math.round(offsetMinutes);
  const sign = eastPositive >= 0 ? "+" : "-";
  return `utc${sign}${Math.abs(eastPositive)}`;
}

export function captureDeviceSignature(): DeviceSignature {
  const userAgent = typeof navigator !== "undefined" ? navigator.userAgent : "";
  let ianaName: string | undefined;
  let offsetMinutes = 0;
  try {
    ianaName = Intl.DateTimeFormat().resolvedOptions().timeZone ?? undefined;
    offsetMinutes = new Date().getTimezoneOffset();
  } catch {
    /* Intl unavailable — the UTC-offset fallback still applies */
  }
  return {
    os: detectOs(userAgent),
    browser: detectBrowser(userAgent),
    timezone: detectTimezone(ianaName, offsetMinutes),
  };
}

export function sameDeviceSignature(
  a: DeviceSignature,
  b: DeviceSignature,
): boolean {
  return a.os === b.os && a.browser === b.browser && a.timezone === b.timezone;
}
