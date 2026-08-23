/**
 * Steam CDN URL classification tests — SBGC-190.
 */

import { describe, expect, it } from "vitest";

import { isSteamCdnUrl } from "./steam-cdn";

describe("isSteamCdnUrl", () => {
  it("recognises the Steam CDN hosts", () => {
    expect(
      isSteamCdnUrl(
        "https://cdn.cloudflare.steamstatic.com/steam/apps/620/library_600x900.jpg",
      ),
    ).toBe(true);
    expect(
      isSteamCdnUrl(
        "https://cdn.akamai.steamstatic.com/steam/apps/620/library_hero.jpg",
      ),
    ).toBe(true);
    expect(
      isSteamCdnUrl(
        "https://steamcdn-a.akamaihd.net/steam/apps/620/header.jpg",
      ),
    ).toBe(true);
    expect(
      isSteamCdnUrl(
        "https://shared.akamai.steamstatic.com/store_item_assets/header.jpg",
      ),
    ).toBe(true);
  });

  it("rejects arbitrary manual origins", () => {
    expect(isSteamCdnUrl("https://example.com/capsule.jpg")).toBe(false);
    expect(isSteamCdnUrl("https://cdn.example.com/hero.jpeg")).toBe(false);
  });

  it("handles empty and malformed input safely", () => {
    expect(isSteamCdnUrl("")).toBe(false);
    expect(isSteamCdnUrl("not-a-url")).toBe(false);
  });
});
