/**
 * Client-side anti-tampering guards — SBGC-218.
 *
 * Applied only on the sign-up page.  These are *client* deterrents — the
 * authoritative state verification happens on the backend (the `challenge_id`
 * must be VERIFIED in cache).  Nothing here is relied upon for security.
 */

export function initAntiTamper(): void {
  // 1. Disable the context menu.
  document.addEventListener("contextmenu", (event) => event.preventDefault());

  // 2. Block common DevTools key combinations.
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "F12" ||
      (event.ctrlKey &&
        event.shiftKey &&
        (event.key === "I" || event.key === "J" || event.key === "C")) ||
      (event.ctrlKey && event.key === "U")
    ) {
      event.preventDefault();
    }
  });

  // 3. Periodic debugger trap: if a debugger pauses execution long enough for
  //    DevTools to be open, redirect to the bot-lockout boundary.
  setInterval(() => {
    const start = performance.now();
    // eslint-disable-next-line no-debugger
    debugger;
    if (performance.now() - start > 100) {
      window.location.href = "/signup-error";
    }
  }, 1000);
}
