# Manual Game Management — SBGC-59

Canonical creation and editing of manual (non-Steam) Games.

## Service

`games/services/manual.py` provides two public operations:

```python
create_manual_game(
    *,
    name: str,
    slug: str | None = None,
    content_type: str = "game",
    listing_status: str = "draft",
    manual_description: str = "",
    manual_image_url: str = "",
    manual_website_url: str = "",
) -> Game

update_manual_game(
    game: Game,
    *,
    name: str | None = None,
    slug: str | None = None,
    content_type: str | None = None,
    listing_status: str | None = None,
    manual_description: str | None = None,
    manual_image_url: str | None = None,
    manual_website_url: str | None = None,
) -> Game
```

`None` in `update_manual_game` means "keep the existing value"; an explicit
value (including `""` for `manual_*`) replaces it.

## Manual identity

The service owns manual identity:

```text
source_type = manual
external_id = NULL
```

It never accepts `source_type`, `external_id`, `steam_image_url`, or
`last_steam_refresh_at` as manual input. Internal `Game.id` remains the
canonical application identity.

## Creation

- `source_type` is forced to `manual`.
- `external_id` is forced to `None`.
- `steam_image_url` stays empty and `last_steam_refresh_at` stays `None`.
- Default `content_type` is `game`; default `listing_status` is `draft`
  (creation never auto-publishes).
- Any existing canonical content type is allowed (`game`, `dlc`, `demo`,
  `software`, `soundtrack`, `unknown`).

## Editing

Only manual Games may be edited. Calling `update_manual_game` on a Steam
Game raises `ManualGameError` before any mutation.

Editable fields: `name`, `slug`, `content_type`, `listing_status`,
`manual_description`, `manual_image_url`, `manual_website_url`.

Preserved: `id`, `source_type`, `external_id`, `steam_image_url`,
`last_steam_refresh_at`, `created_at`, and the editorial classification.
Source conversion is not allowed.

## Slug policy

- If an explicit `slug` is provided, it is used as-is (validated by the
  model).
- Otherwise the slug is `slugify(name)`, truncated to 255 characters.
- A blank slug (e.g. Unicode-only name) requires an explicit slug.
- **Name changes preserve the existing slug.** An explicit `slug` change is
  the only way to update it.
- Slug collisions are rejected (via `full_clean()` / unique validation) —
  they never merge or overwrite another Game.
- No random suffixes.

## Listing

Listing reuses the existing canonical rule:

```python
Game.objects.publicly_listable()
# == content_type == GAME AND listing_status == PUBLISHED
```

A published manual Game is publicly listable; a published manual non-Game
(DLC/Demo/Software/Soundtrack/Unknown) is excluded.

## Classification preservation

Editing a manual Game never touches its `EditorialClassification`,
`ChallengeProfile`, or `RewardProfile`.

## Validation and transactions

The service uses `Game.full_clean()` (field + model + unique validation)
before `save()` inside `transaction.atomic()`. Database constraints remain
authoritative for source/external identity and slug uniqueness.

## No network

Manual CRUD never imports or instantiates Steam services and never makes a
network call.

## Admin

`GameAdmin` makes `source_type` readonly when editing an existing manual
Game, preventing manual → Steam conversion. Steam external-ID editing is
unchanged.

## Out of scope

Delete, soft delete, archive/restore, bulk create/edit, and frontend UI are
not implemented by SBGC-59.
