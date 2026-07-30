# Backend Security

Security configuration for the MyGameDNA Django backend — SBGC-41.

## Threat Model

MyGameDNA is a low-traffic public portfolio application (approximately 100
visits/month). The primary threats are:

- **Credential exposure** — leaked `SECRET_KEY` or `DATABASE_URL` through
  committed files, logs, or misconfigured deployment.
- **CSRF** — cookie-authenticated Django Admin requests from untrusted origins.
- **Host-header poisoning** — requests with forged `Host` headers bypassing
  `ALLOWED_HOSTS`.
- **Information disclosure** — debug stack traces or configuration in
  production error responses.
- **Brute-force** — repeated login attempts against the Admin.

Volumetric DDoS, WAF-level attacks, and supply-chain compromise are
acknowledged but deferred to the deployment provider (Render/Neon).

## Environment Boundary

| Setting | Development | Production | Test |
|---------|------------|------------|------|
| `DEBUG` | `True` | `False` | `True` |
| `SECRET_KEY` | Env or dev fallback | **Required** (validated) | Deterministic |
| `ALLOWED_HOSTS` | `127.0.0.1, localhost` | **Required** (validated) | `testserver, 127.0.0.1, localhost` |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:4321` | **Required** (HTTPS only) | `http://testserver` |
| `DATABASE_URL` | Optional → SQLite | **Required** → PostgreSQL | SQLite in-memory |
| `SECURE_SSL_REDIRECT` | `False` | `True` | `False` |
| `SESSION_COOKIE_SECURE` | `False` | `True` | `False` |
| `SECURE_HSTS_SECONDS` | `0` | `0` (staged) | `0` |
| `NINJA_API_DOCS_ENABLED` | `True` | `False` | `True` |

**Production fails at startup** (raises `ImproperlyConfigured`) when any
required security value is missing, blank, or malformed.

## Secret Key

- **Production:** Must be set via `DJANGO_SECRET_KEY` in the Render
  environment. Rejects missing, blank, known placeholder, or trivially
  short values. Validated by `config.security.validate_secret_key()`.
- **Development:** Uses the committed placeholder if no env var is set.
- **Test:** Uses a deterministic test-only value.
- **Generation:** `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- **Never committed, logged, or included in error messages.**

## Allowed Hosts

- Validated by `config.security.parse_allowed_hosts()`.
- Rejects wildcards (`*`), URLs with schemes, paths, queries, fragments,
  credentials, blank entries, and malformed values.
- Deduplicates entries.
- **Production:** Must include the Render hostname (e.g.,
  `your-app.onrender.com`).

## CSRF Trusted Origins

- Validated by `config.security.parse_trusted_origins()`.
- **Production:** Must use `https://` origins. Rejects HTTP origins,
  malformed URLs, paths, queries, and fragments.
- Trusted origins enable CSRF cookie-authenticated requests (Admin forms).
- Server-to-server Astro→Django traffic does not use CSRF cookies.

## CORS — Explicit Deny-by-Default

- **No CORS middleware is installed.**
- **No `Access-Control-Allow-Origin` response header is returned** for
  any request.
- The architecture requires no browser-to-Django cross-origin access
  (Browser → Astro SSR → Django).
- A future approved browser-to-Django feature must introduce a narrowly
  validated explicit origin allowlist via `django-cors-headers`.

## Password Hashing

Only **PBKDF2-SHA256** is configured:

```
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
```

No MD5, SHA-1, PBKDF2-SHA1, Argon2, bcrypt, or scrypt. The default
PBKDF2 iteration count is preserved. No custom hashers.

## HTTPS and Proxy

- **Render proxy:** `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
  per [Render's Django deployment guide](https://render.com/docs/deploy-django#production-settings).
- **SSL redirect:** `SECURE_SSL_REDIRECT = True`
- Development uses plain HTTP.

## Secure Cookies

| Setting | Production |
|---------|-----------|
| `SESSION_COOKIE_SECURE` | `True` |
| `CSRF_COOKIE_SECURE` | `True` |
| `SESSION_COOKIE_HTTPONLY` | `True` |
| `SESSION_COOKIE_SAMESITE` | `Lax` |
| `CSRF_COOKIE_SAMESITE` | `Lax` |

## HSTS — Staged Rollout

- Default: `SECURE_HSTS_SECONDS = 0` (disabled until deployment verified).
- Stage 1: `3600` (1 hour) — after initial HTTPS deployment verification.
- Stage 2: `31536000` (1 year) — after sustained successful HTTPS operation.
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = False`
- `SECURE_HSTS_PRELOAD = False`

Controlled by `DJANGO_SECURE_HSTS_SECONDS` — a non-negative integer.

## Response Headers

| Setting | Value |
|---------|-------|
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` |
| `X_FRAME_OPTIONS` | `DENY` |
| `SECURE_REFERRER_POLICY` | `strict-origin-when-cross-origin` |
| `SECURE_CROSS_ORIGIN_OPENER_POLICY` | `same-origin` |

No custom response middleware — Django settings provide the behaviour.

## Request-Size Limits

| Setting | Value |
|---------|-------|
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | 2,621,440 (2.5 MiB) |
| `FILE_UPLOAD_MAX_MEMORY_SIZE` | 2,621,440 (2.5 MiB) |
| `DATA_UPLOAD_MAX_NUMBER_FIELDS` | 1,000 |
| `DATA_UPLOAD_MAX_NUMBER_FILES` | 20 |

Conservative values for JSON API payloads and Admin forms. No public
file uploads; Steam images are hotlinked.

## Rate-Limiting

**Current state:** No application-level rate limiting is implemented.

- Login brute-force protection belongs at the deployment/reverse-proxy
  edge or in a later shared-cache-backed control.
- Django Ninja's cache-based throttling is an application fairness
  control, not a security boundary — it may be added for expensive or
  sensitive endpoints in a later ticket.
- Volumetric attack protection is infrastructure-level.
- No Redis, database-backed counters, or process-local lockout is added.

`check --deploy` will warn about the absence of rate limiting. This is a
**documented deployment blocker** — resolved by configuring Render-level
or edge-level protection before public launch.

## Production Deployment Blockers

The following must be resolved before public deployment:

1. **Real `DJANGO_SECRET_KEY`** — generated via `get_random_secret_key()`.
2. **Real `DATABASE_URL`** — direct Neon PostgreSQL connection string.
3. **Real `DJANGO_ALLOWED_HOSTS`** — Render hostname.
4. **Real `CSRF_TRUSTED_ORIGINS`** — `https://` Render origin.
5. **Login rate-limiting** — at the deployment/reverse-proxy edge.
6. **HSTS staged rollout** — set `DJANGO_SECURE_HSTS_SECONDS=3600` after
   initial HTTPS deployment verification.

## Incident Response — Leaked Secret Key

If the `DJANGO_SECRET_KEY` is exposed:

1. Rotate the secret immediately in the Render environment.
2. Invalidate all user sessions (`manage.py clearsessions`).
3. Regenerate and redeploy.
4. Audit access logs for the exposure window.
5. Consider rotating database credentials if the same environment was
   compromised.

## `check --deploy` Output

Running `manage.py check --deploy --settings=config.settings.production`
with valid dummy values produces:

- **W004** (HSTS seconds = 0) — expected; staged rollout.
- **W009** (secret key characteristics) — expected for test values;
  a real generated secret will pass.

No other warnings or errors. These are documented, not silenced.
