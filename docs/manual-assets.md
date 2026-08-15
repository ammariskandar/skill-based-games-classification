# Manual Assets — SBGC-60

Canonical handling of editor-supplied manual image references.

## Scope

SBGC-60 is **URL-only**:

> Support validated external image URLs and fallbacks without unnecessary
> storage.

No uploads, no binary storage, no fetch, no proxy, no CDN, no media model.

## Field ownership

| Field | Owner | Meaning |
|-------|-------|---------|
| `manual_image_url` | Manual/editorial | Editor-supplied image URL for manual records or editorial overrides. |
| `steam_image_url` | Steam import | Validated Steam header-image URL. Readonly in Admin. |

The two fields stay independent:

- manual workflows never mutate `steam_image_url` or `last_steam_refresh_at`;
- Steam import/refresh never mutates `manual_image_url`.

## Validation

`games/services/assets.py` provides the single manual-asset validator:

```python
validate_manual_image_url(value: str) -> str
```

Rules:

- blank/whitespace → `""` (no manual image)
- valid HTTPS URL → returned as-is (outer whitespace stripped)
- anything else → `ManualAssetError`

Specifically rejected:

- non-string input
- `http`, `ftp`, `javascript`, `file`, `data`, and any non-HTTPS scheme
- credentials/userinfo
- missing hostname
- control characters

The model `URLField(max_length=500)` additionally enforces URL shape and
length.  `Game.clean()` calls the validator so Admin, the manual service,
and any future consumer share one validation path.

The validator is **purely structural** — no network access, no DNS, no
HEAD/GET, no availability check.  A valid reference is safe to store/display
as a URL; it is **not** fetch authorization for a future backend fetcher.

## Clear/replace semantics

The manual service keeps its SBGC-59 partial-update contract:

```text
omitted      → keep existing manual_image_url
"" (empty)   → clear manual_image_url
valid URL    → replace manual_image_url
```

## Effective image

`Game.display_image_url` is the pure presentation-neutral fallback helper:

```python
manual_image_url or steam_image_url
```

- manual Game: `manual_image_url` if set, otherwise no image;
- Steam Game: manual override when set, otherwise `steam_image_url`.

It performs no network and no extra database query.

## Not in scope

```text
file/ImageField uploads
binary storage
object storage
CDN/proxy/fetch
thumbnail pipeline
availability checks
frontend rendering
```
