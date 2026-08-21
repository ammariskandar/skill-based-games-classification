/**
 * Presentation-only helpers for the Game Information dialog (SBGC-73).
 *
 * Pure TypeScript — no fetch, no Django domain policy. Shapes the SBGC-71
 * public Game DTO into user-facing metadata rows and a safe release-date
 * string.
 */

import type { GameDetailGame } from "./server/api/games";

export interface GameInformationRow {
  label: string;
  value: string;
}

/** Format a `YYYY-MM-DD` date as "19 April 2011" without timezone day shift. */
export function formatReleaseDate(iso: string): string {
  const parts = iso.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) {
    return iso;
  }
  const [year, month, day] = parts;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

/** Build user-relevant metadata rows, omitting unavailable values. */
export function gameInformationRows(
  game: GameDetailGame,
): GameInformationRow[] {
  const rows: GameInformationRow[] = [];

  if (game.developer) {
    rows.push({ label: "Developer", value: game.developer });
  }
  if (game.release_date) {
    rows.push({
      label: "Release date",
      value: formatReleaseDate(game.release_date),
    });
  }

  rows.push({
    label: "Source",
    value: game.source === "steam" ? "Steam" : "Manual",
  });

  if (game.source === "steam" && game.external_id) {
    rows.push({ label: "Steam App ID", value: game.external_id });
  }

  return rows;
}
