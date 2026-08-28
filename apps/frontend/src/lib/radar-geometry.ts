/**
 * Pure radar-chart geometry (SBGC-85).
 *
 * No DOM dependencies — every helper is a deterministic pure function so the
 * trigonometry and spline generation are fully unit-testable in Node/Vitest.
 */

import { curveCardinalClosed, line } from "d3";
import type {
  DimensionId,
  SkillProfileKind,
  SkillProfileVector,
} from "./skill-dimensions";

export interface Point {
  x: number;
  y: number;
}

export interface SpokeDef {
  kind: SkillProfileKind;
  dimension: DimensionId;
  angleDegrees: number;
}

/**
 * The six canonical radar spokes at 60° intervals (0° = 12 o'clock, clockwise).
 *
 * Challenge and Reward interleave so that each dimension is diametrically
 * opposite its cross-profile twin:
 *
 * - Challenge Micro (0°)   ↔ Reward Micro (180°)
 * - Reward Macro (60°)     ↔ Challenge Macro (240°)
 * - Challenge Mystiko (120°) ↔ Reward Mystiko (300°)
 */
export const SPOKES: readonly SpokeDef[] = [
  { kind: "challenge", dimension: "micro", angleDegrees: 0 },
  { kind: "reward", dimension: "macro", angleDegrees: 60 },
  { kind: "challenge", dimension: "mystiko", angleDegrees: 120 },
  { kind: "reward", dimension: "micro", angleDegrees: 180 },
  { kind: "challenge", dimension: "macro", angleDegrees: 240 },
  { kind: "reward", dimension: "mystiko", angleDegrees: 300 },
];

/**
 * Convert polar coordinates to SVG Cartesian coordinates.
 *
 * 0° is at 12 o'clock and angles increase clockwise (the SVG y-axis points
 * down, so this is a clockwise rotation in screen space).
 */
export function polarToCartesian(
  centerX: number,
  centerY: number,
  radius: number,
  angleInDegrees: number,
): Point {
  const radians = (angleInDegrees * Math.PI) / 180;
  return {
    x: centerX + radius * Math.sin(radians),
    y: centerY - radius * Math.cos(radians),
  };
}

/** Resolve the canonical angle for a (profile, dimension) spoke. */
export function getSpokeAngle(
  kind: SkillProfileKind,
  dimension: DimensionId,
): number {
  const spoke = SPOKES.find(
    (entry) => entry.kind === kind && entry.dimension === dimension,
  );
  if (!spoke) {
    throw new Error(`No radar spoke defined for ${kind}/${dimension}`);
  }
  return spoke.angleDegrees;
}

/**
 * Map a profile's three scores (0–100) to Cartesian vertex points, ordered by
 * spoke angle so the closed spline traces a clean non-self-intersecting shape.
 */
export function getSpokePoints(
  profile: SkillProfileVector,
  kind: SkillProfileKind,
  center: Point,
  maxRadius: number,
): Point[] {
  return SPOKES.filter((spoke) => spoke.kind === kind).map((spoke) => {
    const score = profile[spoke.dimension];
    // Defensive: missing or non-numeric dimensions degrade to 0 so a partial
    // or malformed vector collapses toward the center instead of emitting NaN
    // into the SVG path. Validation happens upstream (skill-dimensions).
    const radius = ((Number.isFinite(score) ? score : 0) / 100) * maxRadius;
    return polarToCartesian(center.x, center.y, radius, spoke.angleDegrees);
  });
}

/**
 * Build a smooth closed SVG path (`d`) through the given points using a
 * cardinal spline. Returns an empty string for empty/null input.
 */
export function generateSplinePath(points: Point[], tension = 0.7): string {
  if (!points || points.length === 0) {
    return "";
  }
  const path = line<Point>()
    .x((point) => point.x)
    .y((point) => point.y)
    .curve(curveCardinalClosed.tension(tension));
  return path(points) ?? "";
}
