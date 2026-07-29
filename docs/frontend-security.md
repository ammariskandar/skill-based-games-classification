# Frontend Security

## Active Security Headers

All routes receive the following headers via `vercel.json`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer leakage to same-origin; cross-origin sends only origin |
| `X-Frame-Options` | `DENY` | Prevents clickjacking via iframe embedding |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), interest-cohort=()` | Disables sensitive browser features universally |
| `Content-Security-Policy` | `frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'` | Minimal CSP: blocks framing, plugins, base-URI override, and cross-origin form submission |

## Astro Built-in Protection

- Astro's `security.checkOrigin` defaults to `true` — requests from mismatched origins are rejected.
- No `allowedDomains` are configured for production until approved hostnames exist.

## Analytics Interaction

- `PUBLIC_GOOGLE_ANALYTICS_ID` is a public measurement ID — not a secret.
- When unset, no Google tag is rendered and no analytics request is made.
- When set, the `vercel.json` CSP does not currently whitelist `googletagmanager.com` or `google-analytics.com`. This must be added when analytics is enabled in production.

## Deferred

| Concern | Status |
|---------|--------|
| Full `default-src` CSP | Deferred — requires testing against Astro/Vercel assets, Google Analytics, and Steam CDN imagery |
| `Cross-Origin-Embedder-Policy` | Deferred — requires `Cross-Origin-Opener-Policy` and impacts shared-array-buffer usage |
| `Cross-Origin-Opener-Policy` | Deferred — may break popup/OAuth flows |
| `Cross-Origin-Resource-Policy` | Deferred — broad policy may block legitimate cross-origin resources |
| HSTS preload | Deferred — requires valid HTTPS certificate and preload submission |
| CSP for analytics | Deferred — add `script-src` and `connect-src` when analytics is enabled |

## Limitations

- `vercel.json` headers apply at the Vercel edge — they are not reproduced in `astro dev`.
- Full CSP testing requires a Vercel preview deployment.
- No runtime security scanner or SAST tool is configured.
- This is a conservative baseline, not a complete security posture.
