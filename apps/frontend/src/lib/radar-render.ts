/**
 * Reusable radar markup builder (SBGC-87).
 *
 * Pure string generation with no DOM dependency. It is the single source of
 * truth for the `<RadarChart>` markup so the same geometry + accessibility
 * markup can be rendered server-side (Astro) and client-side (rankings dynamic
 * selection) without drifting.
 */

import {
  DIMENSIONS,
  buildRadarDescription,
  buildRadarSummaryRows,
  buildRadarTitle,
  buildVertexAriaLabel,
  buildVertexLabel,
  type SkillProfileKind,
  type SkillProfileVector,
} from "./skill-dimensions";
import {
  SPOKES,
  generateSplinePath,
  getSpokePoints,
  polarToCartesian,
  type Point,
} from "./radar-geometry";

export interface RadarRenderData {
  challenge: SkillProfileVector | null;
  reward: SkillProfileVector | null;
  initialProfile?: SkillProfileKind;
  size?: number;
  gameTitle?: string;
  class?: string;
  showToggle?: boolean;
}

const escapeHtml = (value: string): string =>
  value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });

const unavailableHtml = (className: string): string =>
  `<div class="radar-chart radar-chart--unavailable${className}" role="img" aria-label="Skill classification unavailable"><div class="radar-chart__unavailable"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="8.5" cy="10" r="1.5" /><path d="M21 15l-5-5L5 20" /></svg><span>Classification unavailable</span></div></div>`;

/**
 * Horizontal anchor for a spoke label so its leading/trailing glyph sits on the
 * spoke tip and the text flows outward (never into the chart).
 */
function textAnchorFor(angleDegrees: number): "start" | "middle" | "end" {
  const radians = (angleDegrees * Math.PI) / 180;
  const x = Math.sin(radians);
  if (Math.abs(x) < 1e-9) return "middle";
  return x > 0 ? "start" : "end";
}

export function buildRadarHtml(data: RadarRenderData): string {
  const {
    challenge,
    reward,
    initialProfile = "challenge",
    size = 320,
    gameTitle,
    class: className = "",
    showToggle = true,
  } = data;

  const classSuffix = className ? ` ${className}` : "";

  if (challenge === null && reward === null) {
    return unavailableHtml(classSuffix);
  }

  const center: Point = { x: size / 2, y: size / 2 };
  // 56 viewBox units of padding (was 48) around the grid gives the axis labels
  // breathing room before the SVG viewBox edge clips their text (SBGC-209).
  const maxRadius = size / 2 - 56;
  const labelRadius = maxRadius + 24;

  // The outermost ring is the highest score across present profiles, rounded
  // up to the nearest 10; inner rings are linear divisions of that maximum.
  const scores: number[] = [];
  if (challenge) {
    scores.push(challenge.micro, challenge.mystiko, challenge.macro);
  }
  if (reward) {
    scores.push(reward.micro, reward.mystiko, reward.macro);
  }
  const highestScore = scores.length > 0 ? Math.max(...scores) : 0;
  const maxScore = Math.max(10, Math.ceil(highestScore / 10) * 10);

  // `getSpokePoints` maps `score / 100` to a radius; scale the radius so that
  // `maxScore` (not 100) lands on the outermost ring.
  const dataMaxRadius = maxRadius * (100 / maxScore);

  const challengePath =
    challenge === null
      ? ""
      : generateSplinePath(
          getSpokePoints(challenge, "challenge", center, dataMaxRadius),
        );
  const rewardPath =
    reward === null
      ? ""
      : generateSplinePath(
          getSpokePoints(reward, "reward", center, dataMaxRadius),
        );

  const gridRadii = [0.2, 0.4, 0.6, 0.8, 1].map((factor) => factor * maxRadius);

  const spokes = SPOKES.map((spoke) => {
    const profile = spoke.kind === "challenge" ? challenge : reward;
    const score = profile ? profile[spoke.dimension] : 0;
    const dimension = DIMENSIONS[spoke.dimension];
    const textAnchor = textAnchorFor(spoke.angleDegrees);
    const symbolFirst = textAnchor !== "end";
    return {
      kind: spoke.kind,
      dimension: spoke.dimension,
      hasProfile: profile !== null,
      score,
      vertex: polarToCartesian(
        center.x,
        center.y,
        (score / maxScore) * maxRadius,
        spoke.angleDegrees,
      ),
      label: polarToCartesian(
        center.x,
        center.y,
        labelRadius,
        spoke.angleDegrees,
      ),
      colorVar: `--color-${dimension.token}`,
      labelText: symbolFirst
        ? `${dimension.symbol} ${dimension.label}`
        : `${dimension.label} ${dimension.symbol}`,
      textAnchor,
    };
  });

  const uid = crypto.randomUUID();
  const titleId = `radar-title-${uid}`;
  const descId = `radar-desc-${uid}`;

  const title = buildRadarTitle(gameTitle);
  const description = buildRadarDescription(challenge, reward);
  const summaryRows = buildRadarSummaryRows(challenge, reward);

  const gridHtml = gridRadii
    .map(
      (radius) =>
        `<circle class="radar-grid-circle" cx="${center.x}" cy="${center.y}" r="${radius}" />`,
    )
    .join("");

  const labelHtml = spokes
    .map((spoke) => {
      const active = spoke.kind === initialProfile;
      return `<text class="radar-axis-label${
        active ? " radar-axis-label--active" : ""
      }" data-profile="${spoke.kind}" data-dimension="${spoke.dimension}" x="${
        spoke.label.x
      }" y="${spoke.label.y}" text-anchor="${
        spoke.textAnchor
      }" dominant-baseline="middle" style="fill: var(${spoke.colorVar});">${
        spoke.labelText
      }</text>`;
    })
    .join("");

  const challengePathHtml =
    challenge === null
      ? ""
      : `<path class="radar-polygon radar-polygon-challenge ${
          initialProfile === "challenge"
            ? "radar-polygon--active"
            : "radar-polygon--inactive"
        }" d="${challengePath}" />`;
  const rewardPathHtml =
    reward === null
      ? ""
      : `<path class="radar-polygon radar-polygon-reward ${
          initialProfile === "reward"
            ? "radar-polygon--active"
            : "radar-polygon--inactive"
        }" d="${rewardPath}" />`;

  const nodeHtml = spokes
    .filter((spoke) => spoke.hasProfile)
    .map(
      (spoke) =>
        `<circle class="radar-vertex-node${
          spoke.kind === initialProfile ? " radar-vertex-node--active" : ""
        }" cx="${spoke.vertex.x}" cy="${spoke.vertex.y}" r="4" tabindex="0" role="img" data-profile="${spoke.kind}" data-dimension="${spoke.dimension}" data-score="${spoke.score}" data-label="${escapeHtml(
          buildVertexLabel(spoke.kind, spoke.dimension),
        )}" aria-label="${escapeHtml(
          buildVertexAriaLabel(spoke.kind, spoke.dimension, spoke.score),
        )}" style="fill: var(${spoke.colorVar});" />`,
    )
    .join("");

  const tableRowsHtml = summaryRows
    .map(
      (row) =>
        `<tr><th scope="row">${row.label}</th><td>${row.micro}</td><td>${row.mystiko}</td><td>${row.macro}</td></tr>`,
    )
    .join("");

  const hasToggle = showToggle && challenge !== null && reward !== null;

  const toggleHtml = hasToggle
    ? `<div class="radar-toggle-group"><button type="button" class="radar-toggle" role="switch" aria-checked="${
        initialProfile === "reward"
      }" aria-label="Active radar profile"><span class="radar-toggle__track" aria-hidden="true"><span class="radar-toggle__thumb"></span></span></button><span class="radar-toggle__label" data-toggle-label>${
        initialProfile === "challenge" ? "Challenge" : "Reward"
      }</span></div>`
    : "";

  return `<div class="radar-chart${classSuffix}" data-radar-chart data-size="${size}" data-initial-profile="${initialProfile}"><svg class="radar-chart__svg" viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="${titleId} ${descId}"><title id="${titleId}">${escapeHtml(
    title,
  )}</title><desc id="${descId}">${escapeHtml(
    description,
  )}</desc><defs><filter id="radar-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter><radialGradient id="radar-fill" cx="50%" cy="50%" r="50%"><stop offset="0%" style="stop-color: var(--color-micro);" /><stop offset="50%" style="stop-color: var(--color-mystiko);" /><stop offset="100%" style="stop-color: var(--color-macro);" /></radialGradient></defs><g class="radar-grid">${gridHtml}</g><g class="radar-labels">${labelHtml}</g><g class="radar-layers" data-radar-layers><g class="radar-polygons" data-radar-polygons>${challengePathHtml}${rewardPathHtml}</g><g class="radar-nodes">${nodeHtml}</g></g></svg><table class="sr-only"><caption>Skill classification scores</caption><thead><tr><th scope="col">Profile</th><th scope="col">Micro</th><th scope="col">Mystiko</th><th scope="col">Macro</th></tr></thead><tbody>${tableRowsHtml}</tbody></table><div class="radar-tooltip" role="tooltip" aria-hidden="true"><span class="radar-tooltip-header"></span><span class="radar-tooltip-value"></span><p class="radar-tooltip-description"></p></div>${toggleHtml}</div>`;
}
