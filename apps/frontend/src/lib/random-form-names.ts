/**
 * Client-side field-name randomization — SBGC-219 follow-up.
 *
 * Chrome/Edge learn autofill from stable (name, type, autocomplete)
 * combinations they see repeatedly across visits to a page.  Server-rendered
 * random names reduce that, but a field can still be matched once the browser
 * has parsed the delivered DOM.  This re-randomizes the `name` attribute on
 * every page load — and again when a page is restored from the back/forward
 * cache — so the field the human actually interacts with carries a name the
 * browser has never seen before.  Remembered-value autofill therefore has no
 * key to match.
 *
 * Values are always read by id and submitted as an explicit JSON payload
 * (never via native form submission), so the randomized names never need to
 * be restored before submitting.
 */

export function randomizeFieldNames(root: ParentNode = document): void {
  const suffix = Math.random().toString(36).slice(2, 10);
  for (const input of root.querySelectorAll<HTMLInputElement>(
    "input[data-randomize-name]",
  )) {
    input.name = `f_${suffix}_${Math.random().toString(36).slice(2, 6)}`;
  }
}

export function enableRandomizedFieldNames(root: ParentNode = document): void {
  randomizeFieldNames(root);
  // Re-randomize again after full load (Chrome can scan the form at several
  // points) and whenever a page is restored from bfcache (which keeps the DOM
  // — and names — of the previous visit).  Every pass yields a name the
  // browser has not seen before on this URL.
  window.addEventListener("load", () => randomizeFieldNames(root));
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) randomizeFieldNames(root);
  });
}
