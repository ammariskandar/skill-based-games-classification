/**
 * Autofill suppression for sensitive recovery forms — SBGC-219.
 *
 * Browsers and password managers pre-fill visible inputs by name / autocomplete
 * heuristics — and can also populate hidden fields — which previously made a
 * real user's recovery request trip the `company_website` honeypot (400).
 *
 * Every visible input on the guarded forms renders with a `readonly` attribute
 * in the SSR HTML so nothing can be auto-filled at page load (autofill engines
 * skip readonly fields).  The attribute is lifted the instant the human
 * focuses a field, so normal typing is unaffected.
 */

export function initAutofillGuard(): void {
  document.addEventListener(
    "focusin",
    (event) => {
      const target = event.target;
      if (
        target instanceof HTMLElement &&
        target.dataset.autofillGuard !== undefined &&
        target.hasAttribute("readonly")
      ) {
        target.removeAttribute("readonly");
      }
    },
    true,
  );
}
