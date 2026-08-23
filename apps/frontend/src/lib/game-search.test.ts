/**
 * Pure autocomplete matcher tests — SBGC-78.
 */

import { describe, expect, it } from "vitest";

import {
  MAX_SEARCH_SUGGESTIONS,
  normalizeQuery,
  searchGames,
} from "./game-search";
import type { GameSearchIndexItem } from "./server/api/games";

function game(slug: string, name: string): GameSearchIndexItem {
  return { slug, name, capsule_url: null, image_url: null };
}

describe("normalizeQuery", () => {
  it("trims and lowercases", () => {
    expect(normalizeQuery("  Elden Ring  ")).toBe("elden ring");
  });

  it("handles empty and whitespace-only input", () => {
    expect(normalizeQuery("")).toBe("");
    expect(normalizeQuery("   ")).toBe("");
  });
});

describe("searchGames", () => {
  const games = [
    game("cave-story", "Cave Story+"),
    game("elden-ring", "ELDEN RING"),
    game("hades", "Hades"),
    game("half-life", "Half-Life 2"),
    game("persona-4", "Persona 4 Golden"),
    game("pokemon", "Pokémon Legends"),
    game("portal", "Portal"),
    game("portal-2", "Portal 2"),
  ];

  it("returns nothing for an empty query", () => {
    expect(searchGames(games, "")).toEqual([]);
    expect(searchGames(games, "   ")).toEqual([]);
  });

  it("matches case-insensitively", () => {
    expect(searchGames(games, "elden").map((g) => g.slug)).toEqual([
      "elden-ring",
    ]);
    expect(searchGames(games, "ELDEN").map((g) => g.slug)).toEqual([
      "elden-ring",
    ]);
  });

  it("ranks prefix matches before substring matches", () => {
    const result = searchGames(games, "portal").map((g) => g.slug);
    expect(result).toEqual(["portal", "portal-2"]);
  });

  it("ranks prefix matches before substring matches across names", () => {
    const result = searchGames(games, "person").map((g) => g.slug);
    expect(result).toEqual(["persona-4"]);
  });

  it("returns substring matches when no prefix exists", () => {
    const result = searchGames(games, "life").map((g) => g.slug);
    expect(result).toEqual(["half-life"]);
  });

  it("caps results at MAX_SEARCH_SUGGESTIONS", () => {
    const many = Array.from({ length: 20 }, (_, i) =>
      game(`g-${i}`, `Game ${i}`),
    );
    expect(searchGames(many, "game")).toHaveLength(MAX_SEARCH_SUGGESTIONS);
  });

  it("preserves stable ordering within each rank", () => {
    const list = [
      game("b", "Zeta"),
      game("a", "Alpha"),
      game("c", "Alpha Plus"),
    ];
    // Input is name-sorted; "Alpha" and "Alpha Plus" are prefix matches, Zeta
    // is not.
    expect(searchGames(list, "alpha").map((g) => g.slug)).toEqual(["a", "c"]);
  });

  it("handles Unicode names", () => {
    expect(searchGames(games, "pokémon").map((g) => g.slug)).toEqual([
      "pokemon",
    ]);
  });

  it("handles punctuation and apostrophes", () => {
    const list = [
      game("cave-story", "Cave Story+"),
      game("assassins", "Assassin's Creed"),
    ];
    expect(searchGames(list, "cave").map((g) => g.slug)).toEqual([
      "cave-story",
    ]);
    expect(searchGames(list, "assassin").map((g) => g.slug)).toEqual([
      "assassins",
    ]);
  });

  it("does no fuzzy matching (exact substring only)", () => {
    expect(searchGames(games, "prtal")).toEqual([]);
    expect(searchGames(games, "eldenx")).toEqual([]);
  });
});
