import { describe, expect, it } from "vitest";

import {
  LOCKOUT_PENDING_BIO,
  LOCKOUT_PENDING_USERNAME,
  isPageRequest,
  moderationRedirect,
} from "./moderation-routing";

describe("moderationRedirect", () => {
  it("uses the backend's exact lowercase status values", () => {
    // Locks the contract with security.models.ReportStatus.
    expect(LOCKOUT_PENDING_USERNAME).toBe("pending_username_change");
    expect(LOCKOUT_PENDING_BIO).toBe("pending_bio_change");
  });

  it("passes through when there is no lockout", () => {
    expect(
      moderationRedirect({
        pathname: "/catalogue",
        status: null,
        username: "u",
      }),
    ).toBeNull();
  });

  it("routes a username lockout to the remediation form", () => {
    expect(
      moderationRedirect({
        pathname: "/catalogue",
        status: LOCKOUT_PENDING_USERNAME,
        username: "u",
      }),
    ).toBe("/remediate/username");
  });

  it("does not redirect away from the remediation form itself", () => {
    expect(
      moderationRedirect({
        pathname: "/remediate/username",
        status: LOCKOUT_PENDING_USERNAME,
        username: "u",
      }),
    ).toBeNull();
  });

  it("lets a locked-out user reach auth surfaces", () => {
    for (const path of ["/login", "/logout", "/signup", "/reset-password"]) {
      expect(
        moderationRedirect({
          pathname: path,
          status: LOCKOUT_PENDING_USERNAME,
          username: "u",
        }),
      ).toBeNull();
    }
  });

  it("routes a bio lockout to the viewer's own profile", () => {
    expect(
      moderationRedirect({
        pathname: "/games",
        status: "pending_bio_change",
        username: "alice",
      }),
    ).toBe("/profile/alice");
  });

  it("does not redirect when a bio-locked user is already on their profile", () => {
    expect(
      moderationRedirect({
        pathname: "/profile/alice",
        status: LOCKOUT_PENDING_BIO,
        username: "alice",
      }),
    ).toBeNull();
  });

  it("does not redirect a bio lockout without a resolvable username", () => {
    expect(
      moderationRedirect({
        pathname: "/games",
        status: LOCKOUT_PENDING_BIO,
        username: null,
      }),
    ).toBeNull();
  });

  it("ignores unknown statuses", () => {
    expect(
      moderationRedirect({
        pathname: "/games",
        status: "SCHEDULED_FOR_DELETION",
        username: "u",
      }),
    ).toBeNull();
  });
});

describe("isPageRequest", () => {
  it("rejects API, internal, and asset paths", () => {
    expect(isPageRequest("/api/reports/user")).toBe(false);
    expect(isPageRequest("/_astro/foo.js")).toBe(false);
    expect(isPageRequest("/assets/avatars/male_1.avif")).toBe(false);
    expect(isPageRequest("/favicon.ico")).toBe(false);
  });

  it("accepts navigational routes", () => {
    expect(isPageRequest("/catalogue")).toBe(true);
    expect(isPageRequest("/profile/alice")).toBe(true);
    expect(isPageRequest("/games/dead-cells")).toBe(true);
  });
});
