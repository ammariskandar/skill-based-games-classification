/**
 * Presentation-only Game Information tests (SBGC-73).
 */

import { describe, expect, it } from "vitest";

import { formatReleaseDate, gameInformationRows } from "./game-information";
import type { GameDetailGame } from "./server/api/games";

function game(overrides: Partial<GameDetailGame> = {}): GameDetailGame {
  return {
    id: 1,
    slug: "portal-2",
    name: "Portal 2",
    source: "steam",
    external_id: "620",
    content_type: "game",
    description: "A puzzle game.",
    release_date: "2011-04-19",
    developer: "Valve",
    image_url: "https://example.com/header.jpg",
    library_hero_url: null,
    library_capsule_url: null,
    metadata_updated_at: "2026-08-21T00:00:00Z",
    ...overrides,
  };
}

describe("formatReleaseDate", () => {
  it("formats an ISO date without a day shift", () => {
    expect(formatReleaseDate("2011-04-19")).toBe("19 April 2011");
  });

  it("returns an unrecognized value unchanged", () => {
    expect(formatReleaseDate("not-a-date")).toBe("not-a-date");
  });
});

describe("gameInformationRows", () => {
  it("includes developer, release date, source, and Steam App ID for Steam", () => {
    expect(gameInformationRows(game())).toEqual([
      { label: "Developer", value: "Valve" },
      { label: "Release date", value: "19 April 2011" },
      { label: "Source", value: "Steam" },
      { label: "Steam App ID", value: "620" },
    ]);
  });

  it("omits the Steam App ID for a Manual game", () => {
    const rows = gameInformationRows(
      game({ source: "manual", external_id: null }),
    );
    expect(rows.map((r) => r.label)).toEqual([
      "Developer",
      "Release date",
      "Source",
    ]);
    expect(rows.find((r) => r.label === "Source")?.value).toBe("Manual");
  });

  it("omits unavailable optional fields", () => {
    const rows = gameInformationRows(
      game({
        source: "manual",
        external_id: null,
        developer: "",
        release_date: null,
      }),
    );
    expect(rows.map((r) => r.label)).toEqual(["Source"]);
  });
});
