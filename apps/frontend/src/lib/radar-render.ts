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
  const maxRadius = size / 2 - 24;
  const labelRadius = maxRadius + 16;

  const challengePath =
    challenge === null
      ? ""
      : generateSplinePath(
          getSpokePoints(challenge, "challenge", center, maxRadius),
        );
  const rewardPath =
    reward === null
      ? ""
      : generateSplinePath(getSpokePoints(reward, "reward", center, maxRadius));

  const gridRadii = [0.25, 0.5, 0.75, 1].map((factor) => factor * maxRadius);

  const spokes = SPOKES.map((spoke) => {
    const profile = spoke.kind === "challenge" ? challenge : reward;
    const score = profile ? profile[spoke.dimension] : 0;
    const dimension = DIMENSIONS[spoke.dimension];
    return {
      kind: spoke.kind,
      dimension: spoke.dimension,
      hasProfile: profile !== null,
      score,
      vertex: polarToCartesian(
        center.x,
        center.y,
        (score / 100) * maxRadius,
        spoke.angleDegrees,
      ),
      endpoint: polarToCartesian(
        center.x,
        center.y,
        maxRadius,
        spoke.angleDegrees,
      ),
      label: polarToCartesian(
        center.x,
        center.y,
        labelRadius,
        spoke.angleDegrees,
      ),
      colorVar: `--color-${dimension.token}`,
      labelText: `${dimension.symbol} ${dimension.label}`,
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

  const spokeHtml = spokes
    .map(
      (spoke) =>
        `<line class="radar-spoke" x1="${center.x}" y1="${center.y}" x2="${spoke.endpoint.x}" y2="${spoke.endpoint.y}" style="stroke: var(${spoke.colorVar});" />`,
    )
    .join("");

  const labelHtml = spokes
    .map(
      (spoke) =>
        `<text class="radar-axis-label" x="${spoke.label.x}" y="${spoke.label.y}" text-anchor="middle" dominant-baseline="middle" style="fill: var(${spoke.colorVar});">${spoke.labelText}</text>`,
    )
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
        `<circle class="radar-vertex-node" cx="${spoke.vertex.x}" cy="${spoke.vertex.y}" r="4" tabindex="0" role="img" data-profile="${spoke.kind}" data-dimension="${spoke.dimension}" data-score="${spoke.score}" data-label="${escapeHtml(
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

  const challengeButtonDisabled = challenge === null ? " disabled" : "";
  const rewardButtonDisabled = reward === null ? " disabled" : "";

  const toggleHtml = showToggle
    ? `<div class="radar-toggle-group" role="group" aria-label="Active Radar Profile"><button type="button" class="radar-toggle-button" data-profile-toggle="challenge" aria-pressed="${
        initialProfile === "challenge"
      }"${challengeButtonDisabled}>Challenge Profile</button><button type="button" class="radar-toggle-button" data-profile-toggle="reward" aria-pressed="${
        initialProfile === "reward"
      }"${rewardButtonDisabled}>Reward Profile</button></div>`
    : "";

  return `<div class="radar-chart${classSuffix}" data-radar-chart data-size="${size}" data-initial-profile="${initialProfile}"><svg class="radar-chart__svg" viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet" role="img" aria-labelledby="${titleId} ${descId}"><title id="${titleId}">${escapeHtml(
    title,
  )}</title><desc id="${descId}">${escapeHtml(
    description,
  )}</desc><defs><filter id="radar-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter><radialGradient id="radar-fill" cx="50%" cy="50%" r="50%"><stop offset="0%" style="stop-color: var(--color-micro);" /><stop offset="50%" style="stop-color: var(--color-mystiko);" /><stop offset="100%" style="stop-color: var(--color-macro);" /></radialGradient></defs><g class="radar-grid">${gridHtml}${spokeHtml}</g><g class="radar-labels">${labelHtml}</g><g class="radar-layers" data-radar-layers><g class="radar-polygons" data-radar-polygons>${challengePathHtml}${rewardPathHtml}</g><g class="radar-nodes">${nodeHtml}</g></g></svg><table class="sr-only"><caption>Skill classification scores</caption><thead><tr><th scope="col">Profile</th><th scope="col">Micro</th><th scope="col">Mystiko</th><th scope="col">Macro</th></tr></thead><tbody>${tableRowsHtml}</tbody></table><div class="radar-tooltip" role="tooltip" aria-hidden="true"><span class="radar-tooltip-header"></span><span class="radar-tooltip-value"></span><p class="radar-tooltip-description"></p></div>${toggleHtml}</div>`;
}
