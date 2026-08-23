/**
 * Steam CDN URL classification — SBGC-190.
 *
 * The browser-side WebSR enhancer needs pixel-read access to the foreground
 * image, which only works when the image is loaded `crossorigin="anonymous"`
 * from a host that sends `Access-Control-Allow-Origin: *`. Steam's CDN does;
 * arbitrary manual override URLs may not. This helper lets the renderer enable
 * `crossorigin` only for the known Steam CDN hosts so a manual override on an
 * arbitrary origin still displays (and enhancement is skipped gracefully).
 *
 * This is a CORS-safety check, not Steam asset-URL *derivation* — Django still
 * owns resolving the effective URL.
 */

const STEAM_CDN_HOST_SUFFIX = ".steamstatic.com";
const STEAM_CDN_AKAMAI_HOST = "steamcdn-a.akamaihd.net";

/** Whether *url* is on a Steam CDN host that reliably sends CORS headers. */
export function isSteamCdnUrl(url: string): boolean {
  if (!url) return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return (
      hostname === STEAM_CDN_AKAMAI_HOST ||
      hostname.endsWith(STEAM_CDN_HOST_SUFFIX)
    );
  } catch {
    return false;
  }
}
