# Django Admin Configuration

MyGameDNA administration interface powered by Django's built-in `django.contrib.admin`.

## Admin Route

The admin is mounted at a path controlled by `ADMIN_URL_PATH`:

```
# Default (in .env.example):
ADMIN_URL_PATH=mygamedna-admin

# Resulting URL:
/mygamedna-admin/
```

The configured value is validated at settings-import time against the
project's path-segment contract.

### ADMIN_URL_PATH Format

| Rule | Example | Status |
|------|---------|--------|
| Single relative path segment | `admin` | Accepted |
| Letters, digits, hyphens, underscores | `my-admin-123` | Accepted |
| Starts with letter or digit | `a1-b2` | Accepted |
| Blank / missing | *(empty)* | Rejected |
| Leading slash | `/admin` | Rejected |
| Trailing slash | `admin/` | Rejected |
| Nested slash | `a/b` | Rejected |
| Backslash | `admin\\hidden` | Rejected |
| Dot segments | `.`, `..` | Rejected |
| Query string | `admin?next=/` | Rejected |
| Fragment | `admin#top` | Rejected |
| Full URL | `https://...` | Rejected |
| Reserved "api" | `api` | Rejected |

Violations raise `django.core.exceptions.ImproperlyConfigured` at startup.
Rejected values are never echoed in error messages.

### Security Note

A non-default admin route is **defence in depth**, not a primary security
control. Full production admin security hardening (rate limiting, staff
IP restrictions, deploy checks) belongs to SBGC-41 and SBGC-106.

## Superuser Creation

Use Django's standard `createsuperuser` management command:

```bash
python manage.py createsuperuser --settings=config.settings.development
```

- Credentials are stored in the configured database (hashed password).
- Never commit superuser credentials, environment values, or fixture data.
- Automated tests create temporary users in the isolated test database only.

## Admin Branding

The default Django AdminSite is branded with MyGameDNA labels:

| Setting | Value |
|---------|-------|
| `site_header` | MyGameDNA Administration |
| `site_title` | MyGameDNA Admin |
| `index_title` | Content administration |

No custom templates, CSS, or AdminSite subclass is used.

## Model Registration

Model admin registrations are **app-owned**:

| App | File | Status |
|-----|------|--------|
| `games` | `games/admin.py` | No models yet (SBGC-4) |
| `classifications` | `classifications/admin.py` | No models yet (SBGC-4) |

Registrations must not be placed in `config/` or `api/`. No speculative
`ModelAdmin` base classes should be created before real, repeated model
requirements exist.

## Search and Filter Conventions

When `ModelAdmin` classes are introduced, follow these conventions:

- **`search_fields`** — only useful human-searchable fields (names, text
  identifiers). Stable external identifiers (Steam app IDs, slugs) should
  use explicit exact lookups.
- **Related search** — use Django relationship traversal (`game__name`)
  where appropriate.
- **`list_filter`** — favour indexed, bounded-cardinality operational
  fields. Avoid expensive high-cardinality sidebar filters.
- **`list_display`** — expose useful operational fields for scanning.
- **Ordering** — must be deterministic; avoid ordering on unindexed fields.
- **`list_select_related`** — use for displayed foreign-key data to avoid
  N+1 queries.
- **Testing** — actual search and filter behaviour must be tested when
  each domain `ModelAdmin` is introduced.

## Bulk Action Conventions

Each future bulk action must:

- Be explicitly opted into by its `ModelAdmin` via `actions`.
- Have an understandable action label (`delete_selected`, `publish_games`).
- Enforce the appropriate model permission.
- Operate only on the selected queryset.
- Provide success or failure feedback via `self.message_user()`.
- Have tests for authorised and unauthorised users.
- Require confirmation for materially destructive or publication-changing
  work (use `actions` with confirmation pages or `@admin.action` with
  `permissions`).
- Use transactions where partial completion would leave inconsistent state.
- Avoid one external Steam API call per selected object — batch where
  possible.
- Avoid per-object save loops when a safe queryset update is correct.

Django's built-in `delete_selected` action is preserved by default. Do not
globally remove it without explicit Jira ownership.

## Current Limitations

- **No domain models registered** — `games/admin.py` and
  `classifications/admin.py` are empty stubs. Model registrations will be
  added in SBGC-4.
- **No custom admin actions** — bulk-action conventions are documented
  but not yet implemented.
- **Full admin security hardening is pending** — rate limiting, staff
  IP restrictions, and deploy checks belong to SBGC-41 and SBGC-106.
- **Admin is not exposed through Astro** — the admin route is a direct
  Django-served path behind the configured `ADMIN_URL_PATH` segment.
