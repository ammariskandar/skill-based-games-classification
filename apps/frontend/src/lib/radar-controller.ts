/**
 * Client-side controller for the dual-profile radar chart (SBGC-85).
 *
 * The Astro component renders the full static SVG server-side; this controller
 * adds progressive enhancement: appear-in animation, profile toggle, and
 * vertex-node hover glow. It returns a cleanup function that detaches every
 * listener and cancels the animation frame.
 */

import type { SkillProfileKind } from "./skill-dimensions";

const ACTIVE_CLASS = "radar-polygon--active";
const INACTIVE_CLASS = "radar-polygon--inactive";
const HOVERED_CLASS = "radar-vertex-node--hovered";

const BASE_NODE_RADIUS = 4;
const HOVERED_NODE_RADIUS = 7;

export function initRadarChart(container: HTMLElement): () => void {
  const size = Number(container.dataset.size ?? "320");
  const initial = (container.dataset.initialProfile ??
    "challenge") as SkillProfileKind;

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
  const buttons = Array.from(
    container.querySelectorAll<HTMLButtonElement>("[data-profile-toggle]"),
  );
  const nodes = Array.from(
    container.querySelectorAll<SVGCircleElement>(".radar-vertex-node"),
  );

  let animationFrame = 0;
  let disposed = false;

  function setActive(profile: SkillProfileKind): void {
    for (const button of buttons) {
      const active = button.dataset.profileToggle === profile;
      button.setAttribute("aria-pressed", String(active));
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

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
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

  function onToggle(event: Event): void {
    const button = event.currentTarget as HTMLButtonElement;
    const profile = button.dataset.profileToggle as SkillProfileKind;
    setActive(profile);
  }

  function onNodeEnter(event: Event): void {
    const node = event.currentTarget as SVGCircleElement;
    node.setAttribute("r", String(HOVERED_NODE_RADIUS));
    node.classList.add(HOVERED_CLASS);
  }

  function onNodeLeave(event: Event): void {
    const node = event.currentTarget as SVGCircleElement;
    node.setAttribute("r", String(BASE_NODE_RADIUS));
    node.classList.remove(HOVERED_CLASS);
  }

  setActive(initial);
  animateAppear();

  for (const button of buttons) {
    button.addEventListener("click", onToggle);
  }
  for (const node of nodes) {
    node.addEventListener("mouseenter", onNodeEnter);
    node.addEventListener("mouseleave", onNodeLeave);
  }

  return () => {
    disposed = true;
    if (animationFrame) {
      cancelAnimationFrame(animationFrame);
    }
    for (const button of buttons) {
      button.removeEventListener("click", onToggle);
    }
    for (const node of nodes) {
      node.removeEventListener("mouseenter", onNodeEnter);
      node.removeEventListener("mouseleave", onNodeLeave);
    }
  };
}
