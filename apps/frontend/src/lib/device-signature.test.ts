/**
 * Device signature tests — SBGC-218 dropoff-resume gate.
 *
 * Pins OS/browser/timezone detection from representative user-agent strings
 * and the timezone fallback, plus same-signature equality used to require the
 * exact system that requested a verification challenge.
 */

import { describe, expect, it } from "vitest";
import {
  captureDeviceSignature,
  detectBrowser,
  detectOs,
  detectTimezone,
  sameDeviceSignature,
  type DeviceSignature,
} from "./device-signature";

describe("detectOs", () => {
  it.each([
    ["android", "Mozilla/5.0 (Linux; Android 14) Mobile Safari/537.36"],
    ["ios", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile"],
    ["windows", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"],
    ["macos", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605"],
    ["chromeos", "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) Chrome/120.0"],
    ["linux", "Mozilla/5.0 (X11; Linux x86_64) Firefox/121.0"],
    ["unknown", "Some Random String"],
  ])("detects %s", (expected, ua) => {
    expect(detectOs(ua)).toBe(expected);
  });
});

describe("detectBrowser", () => {
  it.each([
    ["chrome", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"],
    ["edge", "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Edg/120.0.0.0"],
    ["firefox", "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Firefox/121.0"],
    [
      "safari",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    ],
    ["opera", "Mozilla/5.0 (Windows NT 10.0) OPR/105.0.0.0"],
    ["unknown", "Some Random String"],
  ])("detects %s", (expected, ua) => {
    expect(detectBrowser(ua)).toBe(expected);
  });
});

describe("detectTimezone", () => {
  it("prefers the IANA name when available", () => {
    expect(detectTimezone("Asia/Kuala_Lumpur", 0)).toBe("Asia/Kuala_Lumpur");
  });

  it("falls back to an east-positive UTC offset", () => {
    expect(detectTimezone(undefined, -480)).toBe("utc+480");
    expect(detectTimezone(undefined, 300)).toBe("utc-300");
    expect(detectTimezone(undefined, 0)).toBe("utc+0");
  });
});

describe("captureDeviceSignature", () => {
  it("always returns all three fields as strings", () => {
    const signature = captureDeviceSignature();
    expect(typeof signature.os).toBe("string");
    expect(typeof signature.browser).toBe("string");
    expect(typeof signature.timezone).toBe("string");
    expect(signature.os.length).toBeGreaterThan(0);
    expect(signature.browser.length).toBeGreaterThan(0);
    expect(signature.timezone.length).toBeGreaterThan(0);
  });
});

describe("sameDeviceSignature", () => {
  const a: DeviceSignature = {
    os: "windows",
    browser: "chrome",
    timezone: "Asia/Kuala_Lumpur",
  };

  it("is true for identical signatures", () => {
    expect(sameDeviceSignature(a, { ...a })).toBe(true);
  });

  it.each([
    ["os", { ...a, os: "macos" }],
    ["browser", { ...a, browser: "firefox" }],
    ["timezone", { ...a, timezone: "Europe/London" }],
  ])("is false when %s differs", (_field, other) => {
    expect(sameDeviceSignature(a, other)).toBe(false);
  });
});
