/**
 * Trusted client IP derivation for the Astro BFF — SBGC-107.
 *
 * The public browser never reaches Django directly: the BFF derives the
 * client IP strictly from the verified edge ingress (`cf-connecting-ip`,
 * overwritten by Cloudflare/the host reverse proxy) and forwards it as
 * `X-Client-Real-IP`.  Raw, user-supplied forwarding headers are never read
 * here, so an untrusted client cannot spoof its identity.
 */
export function getTrustedClientIp(request: Request): string {
  const edgeIp = request.headers.get("cf-connecting-ip");
  if (edgeIp) return edgeIp.trim();
  // Direct Node development without edge termination.
  return "127.0.0.1";
}
