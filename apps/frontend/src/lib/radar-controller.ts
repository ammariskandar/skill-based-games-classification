/**
 * Client-side controller for the dual-profile radar chart (SBGC-85/86).
 *
 * The Astro component renders the full static SVG server-side; this controller
 * adds progressive enhancement: appear-in animation (reduced-motion aware),
 * profile toggle, vertex-node hover/focus tooltips + glow, and a cleanup
 * function that detaches every listener and cancels the animation frame.
 */

import {
  getDimensionDescription,
  type DimensionId,
  type SkillProfileKind,
} from "./skill-dimensions";

const ACTIVE_CLASS = "radar-polygon--active";
const INACTIVE_CLASS = "radar-polygon--inactive";
const HOVERED_CLASS = "radar-vertex-node--hovered";

const BASE_NODE_RADIUS = 4;
const HOVERED_NODE_RADIUS = 7;

/**
 * Pure reduced-motion check, injectable for Node/Vitest. Returns `true` when
 * the caller's media query matches `prefers-reduced-motion: reduce`.
 */
export function prefersReducedMotion(
  matchMedia: (query: string) => { matches: boolean },
): boolean {
  return matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function initRadarChart(container: HTMLElement): () => void {
  const size = Number(container.dataset.size ?? "320");
  const initial = (container.dataset.initialProfile ??
    "challenge") as SkillProfileKind;

  const svg = container.querySelector<SVGSVGElement>("svg");
  const layers = container.querySelector<SVGGElement>("[data-radar-layers]");
  const polygonGroup = container.querySelector<SVGGElement>(
    "[data-radar-polygons]",
  );
  const challengePath = container.querySelector<SVGPathElement>(
    ".radar-polygon-challenge",
  );
  const rewardPath = container.querySelector<SVGPathElement>(
    ".radar-polygon-reward",
  );
  const toggles = Array.from(
    container.querySelectorAll<HTMLInputElement>("[data-profile-toggle]"),
  );
  const nodes = Array.from(
    container.querySelectorAll<SVGCircleElement>(".radar-vertex-node"),
  );
  const axisLabels = Array.from(
    container.querySelectorAll<SVGTextElement>(".radar-axis-label"),
  );
  const tooltip = container.querySelector<HTMLElement>(".radar-tooltip");
  const tooltipHeader = tooltip?.querySelector<HTMLElement>(
    ".radar-tooltip-header",
  );
  const tooltipValue = tooltip?.querySelector<HTMLElement>(
    ".radar-tooltip-value",
  );
  const tooltipDescription = tooltip?.querySelector<HTMLElement>(
    ".radar-tooltip-description",
  );

  let animationFrame = 0;
  let disposed = false;

  function setActive(profile: SkillProfileKind): void {
    for (const toggle of toggles) {
      toggle.checked = toggle.dataset.profileToggle === profile;
    }
    for (const label of axisLabels) {
      label.classList.toggle(
        "radar-axis-label--active",
        label.dataset.profile === profile,
      );
    }

    if (challengePath) {
      challengePath.classList.toggle(ACTIVE_CLASS, profile === "challenge");
      challengePath.classList.toggle(INACTIVE_CLASS, profile !== "challenge");
    }
    if (rewardPath) {
      rewardPath.classList.toggle(ACTIVE_CLASS, profile === "reward");
      rewardPath.classList.toggle(INACTIVE_CLASS, profile !== "reward");
    }

    // SVG paints in document order, so moving the active path to the end puts
    // it on top without re-mounting the DOM.
    const activePath = profile === "challenge" ? challengePath : rewardPath;
    if (polygonGroup && activePath) {
      polygonGroup.appendChild(activePath);
    }
  }

  function animateAppear(): void {
    if (!layers) return;

    if (prefersReducedMotion((query) => window.matchMedia(query))) {
      return;
    }

    const cx = size / 2;
    const cy = size / 2;
    const duration = 600;
    const start = performance.now();

    const apply = (scale: number): void => {
      layers.setAttribute(
        "transform",
        `translate(${cx} ${cy}) scale(${scale}) translate(${-cx} ${-cy})`,
      );
    };

    apply(0);

    const frame = (now: number): void => {
      if (disposed) return;
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      apply(eased);
      if (progress < 1) {
        animationFrame = requestAnimationFrame(frame);
      } else {
        layers.removeAttribute("transform");
      }
    };

    animationFrame = requestAnimationFrame(frame);
  }

  function scale(): number {
    if (!svg) return 1;
    return svg.clientWidth / size;
  }

  function showTooltip(node: SVGCircleElement): void {
    if (!tooltip) return;

    const dimension = node.dataset.dimension as DimensionId;
    const profile = node.dataset.profile as SkillProfileKind;
    const score = Number(node.dataset.score ?? 0);
    const label = node.dataset.label ?? "";

    const cx = Number(node.getAttribute("cx") ?? 0);
    const cy = Number(node.getAttribute("cy") ?? 0);
    const chartScale = scale();
    const nodeX = cx * chartScale;
    const nodeY = cy * chartScale;

    if (tooltipHeader) {
      tooltipHeader.textContent = label;
      tooltipHeader.style.color = `var(--color-${dimension})`;
    }
    if (tooltipValue) {
      tooltipValue.textContent = `${score}%`;
    }
    if (tooltipDescription) {
      tooltipDescription.textContent = getDimensionDescription(
        profile,
        dimension,
      );
    }

    tooltip.setAttribute("aria-hidden", "false");
    tooltip.style.opacity = "1";

    const width = tooltip.offsetWidth;
    const height = tooltip.offsetHeight;
    const gap = 12;

    // The SVG is narrower than the wrapper (75% width, centered), so translate
    // node coordinates into the wrapper's coordinate space before clamping the
    // tooltip within the SVG bounds.
    const chartSize = svg ? svg.clientWidth : size;
    const offsetX = svg
      ? svg.getBoundingClientRect().left -
        container.getBoundingClientRect().left
      : 0;
    const offsetY = svg
      ? svg.getBoundingClientRect().top - container.getBoundingClientRect().top
      : 0;

    let top = offsetY + nodeY - height - gap;
    if (top < offsetY) top = offsetY + nodeY + gap;
    top = Math.max(offsetY, Math.min(top, offsetY + chartSize - height));

    let left = offsetX + nodeX - width / 2;
    left = Math.max(offsetX, Math.min(left, offsetX + chartSize - width));

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
  }

  function hideTooltip(): void {
    if (!tooltip) return;
    tooltip.setAttribute("aria-hidden", "true");
    tooltip.style.opacity = "0";
  }

  function showNode(node: SVGCircleElement): void {
    node.setAttribute("r", String(HOVERED_NODE_RADIUS));
    node.classList.add(HOVERED_CLASS);
    showTooltip(node);
  }

  function hideNode(node: SVGCircleElement): void {
    node.setAttribute("r", String(BASE_NODE_RADIUS));
    node.classList.remove(HOVERED_CLASS);
    hideTooltip();
  }

  function onToggle(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    if (!input.checked) return;
    setActive(input.dataset.profileToggle as SkillProfileKind);
  }

  function onNodeShow(event: Event): void {
    showNode(event.currentTarget as SVGCircleElement);
  }

  function onNodeHide(event: Event): void {
    hideNode(event.currentTarget as SVGCircleElement);
  }

  setActive(initial);
  animateAppear();

  for (const toggle of toggles) {
    toggle.addEventListener("change", onToggle);
  }
  for (const node of nodes) {
    node.addEventListener("mouseenter", onNodeShow);
    node.addEventListener("mouseleave", onNodeHide);
    node.addEventListener("focus", onNodeShow);
    node.addEventListener("blur", onNodeHide);
  }

  return () => {
    disposed = true;
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
    }
    for (const toggle of toggles) {
      toggle.removeEventListener("change", onToggle);
    }
    for (const node of nodes) {
      node.removeEventListener("mouseenter", onNodeShow);
      node.removeEventListener("mouseleave", onNodeHide);
      node.removeEventListener("focus", onNodeShow);
      node.removeEventListener("blur", onNodeHide);
    }
  };
}
