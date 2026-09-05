/**
 * Client-side field-identity randomization — SBGC-219 follow-up.
 *
 * Chrome/Edge learn autofill from recurring field signatures they see across
 * visits.  A signature is built from the field's *name*, its *id*, its type,
 * and its autocomplete attribute — so randomizing only `name` still leaves a
 * stable `id` (e.g. `reset-email`) for the browser to match remembered values
 * against.  This re-randomizes **both** `name` and `id` on every page load
 * (and again on `load` and on back/forward-cache `pageshow` restore), so the
 * field the human actually interacts with has an identity the browser has
 * never seen on that URL.
 *
 * Reverse references (`<label for>`, `aria-labelledby`) are rewritten in the
 * same pass so accessibility and label-click focus keep working.  Values are
 * always read from captured element references and submitted as an explicit
 * JSON payload (never via native form submission), so the randomized names
 * never need to be restored before submitting.
 */

export function randomizeFieldNames(root: ParentNode = document): void {
  const suffix = Math.random().toString(36).slice(2, 10);
  for (const input of root.querySelectorAll<HTMLInputElement>(
    "input[data-randomize-name]",
  )) {
    const oldId = input.id;
    const newId = `fid_${suffix}_${Math.random().toString(36).slice(2, 6)}`;
    if (oldId) {
      for (const label of Array.from(
        root.querySelectorAll(`label[for="${oldId}"]`),
      )) {
        label.setAttribute("for", newId);
      }
      for (const el of Array.from(
        root.querySelectorAll(`[aria-labelledby="${oldId}"]`),
      )) {
        el.setAttribute("aria-labelledby", newId);
      }
    }
    input.id = newId;
    input.name = `f_${suffix}_${Math.random().toString(36).slice(2, 6)}`;
  }
}

export function enableRandomizedFieldNames(root: ParentNode = document): void {
  randomizeFieldNames(root);
  // Re-randomize again after full load (Chrome can scan the form at several
  // points) and whenever a page is restored from bfcache (which keeps the DOM
  // — and field identities — of the previous visit).  Every pass yields an id
  // + name combination the browser has not seen before on this URL.
  window.addEventListener("load", () => randomizeFieldNames(root));
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) randomizeFieldNames(root);
  });
}
