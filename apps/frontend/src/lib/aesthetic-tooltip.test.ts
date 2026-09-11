// @vitest-environment jsdom
/**
 * Aesthetic tooltip controller tests — SBGC-228.
 *
 * Locks the accessible open/close contract: aria-expanded reflects state,
 * focus and click open it, and Escape / an outside pointer press dismiss it.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { mountAestheticTooltip } from "./aesthetic-tooltip";
import type { AestheticTooltipController } from "./aesthetic-tooltip";

describe("mountAestheticTooltip", () => {
  let root: HTMLElement;
  let trigger: HTMLButtonElement;
  let panel: HTMLElement;
  let controller: AestheticTooltipController;

  beforeEach(() => {
    root = document.createElement("span");
    trigger = document.createElement("button");
    trigger.setAttribute("aria-expanded", "false");
    panel = document.createElement("div");
    panel.hidden = true;
    root.append(trigger, panel);
    document.body.append(root);
    controller = mountAestheticTooltip(root, trigger, panel, document);
  });

  afterEach(() => {
    controller.destroy();
    root.remove();
  });

  it("starts collapsed", () => {
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(panel.hidden).toBe(true);
    expect(controller.isOpen()).toBe(false);
  });

  it("opens on focus and closes on focus out", () => {
    root.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(panel.hidden).toBe(false);

    root.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(panel.hidden).toBe(true);
  });

  it("opens on click/tap", () => {
    trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(panel.hidden).toBe(false);
  });

  it("dismisses on Escape and returns focus to the trigger", () => {
    trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));

    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(panel.hidden).toBe(true);
    expect(document.activeElement).toBe(trigger);
  });

  it("dismisses on an outside pointer press", () => {
    trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    document.dispatchEvent(new Event("pointerdown", { bubbles: true }));

    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("stays open for a pointer press inside the tooltip", () => {
    trigger.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    panel.dispatchEvent(new Event("pointerdown", { bubbles: true }));

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
  });
});
