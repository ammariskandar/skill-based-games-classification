/**
 * Accessible tooltip controller — SBGC-228.
 *
 * Framework-free open/close state for the aesthetic definition card.  Opens on
 * pointer hover and keyboard focus, opens on click/tap (mobile has no hover),
 * and dismisses on Escape or an outside pointer press.  Being DOM-only makes it
 * unit-testable under jsdom.
 */

export interface AestheticTooltipController {
  open(): void;
  close(): void;
  isOpen(): boolean;
  destroy(): void;
}

export function mountAestheticTooltip(
  root: HTMLElement,
  trigger: HTMLElement,
  panel: HTMLElement,
  doc: Document = document,
): AestheticTooltipController {
  let open = false;

  function render(): void {
    panel.hidden = !open;
    trigger.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function setOpen(next: boolean): void {
    if (open === next) return;
    open = next;
    render();
  }

  function contains(node: Node | null): boolean {
    return node !== null && root.contains(node);
  }

  // Hover and mouse-leave.  A pointer click focuses the trigger, so the
  // activeElement guard keeps a clicked-open card pinned until Escape/outside.
  const onMouseEnter = () => setOpen(true);
  const onMouseLeave = () => {
    if (!contains(doc.activeElement)) setOpen(false);
  };

  // Keyboard focus opens; moving focus within the root reopens via focusin.
  const onFocusIn = () => setOpen(true);
  const onFocusOut = () => setOpen(false);

  // Click/tap explicitly opens (mobile viewports have no hover).
  const onClick = () => setOpen(true);

  const onKeyDown = (event: Event) => {
    const key = (event as KeyboardEvent).key;
    if (key === "Escape" && open) {
      // Focus first: returning focus can itself fire `focusin`, so close after.
      trigger.focus();
      setOpen(false);
    }
  };

  const onPointerDown = (event: Event) => {
    if (open && !contains(event.target as Node)) setOpen(false);
  };

  root.addEventListener("mouseenter", onMouseEnter);
  root.addEventListener("mouseleave", onMouseLeave);
  root.addEventListener("focusin", onFocusIn);
  root.addEventListener("focusout", onFocusOut);
  trigger.addEventListener("click", onClick);
  doc.addEventListener("keydown", onKeyDown);
  doc.addEventListener("pointerdown", onPointerDown);

  render();

  return {
    open: () => setOpen(true),
    close: () => setOpen(false),
    isOpen: () => open,
    destroy() {
      root.removeEventListener("mouseenter", onMouseEnter);
      root.removeEventListener("mouseleave", onMouseLeave);
      root.removeEventListener("focusin", onFocusIn);
      root.removeEventListener("focusout", onFocusOut);
      trigger.removeEventListener("click", onClick);
      doc.removeEventListener("keydown", onKeyDown);
      doc.removeEventListener("pointerdown", onPointerDown);
    },
  };
}
