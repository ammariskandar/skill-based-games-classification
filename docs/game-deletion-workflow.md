# Game Deletion Workflow — SBGC-182

Canonical hard-deletion behavior for `Game`.

## Semantics

- **Hard delete**, not soft delete.  No tombstone, no archive redefinition.
- Archive/hide remains the reversible editorial `listing_status=archived`.
  Archive is **not** deletion.
- Source parity: both manual and Steam Games are deletable locally.
- No network: deletion never contacts Steam or any external service.
- No API: SBGC-6 manual management remains Admin/service-only.

## Service

`games/services/deletion.py`:

```python
delete_game(game: Game) -> GameDeletionResult
```

`GameDeletionResult` records the pre-deletion identity (`game_id`,
`source_type`, `slug`).  The service validates a saved `Game`, runs the
delete inside a short transaction, and delegates the relational cascade to
Django's collector.

## Cascade graph

```text
Game
└── EditorialClassification   (OneToOne, CASCADE)
    ├── ChallengeProfile       (OneToOne, CASCADE)
    └── RewardProfile          (OneToOne, CASCADE)
```

Deleting a Game cascades its editorial classification and both profiles.
`updated_by` (User) is `PROTECT` and is **never** deleted by this cascade.

## Admin

- Django's built-in single-object deletion confirmation is used.
- The confirmation lists related objects that will be deleted.
- Bulk `delete_selected` is disabled for `GameAdmin`; deletion remains a
  deliberate single-object operation.
- Permission uses Django's standard `games.delete_game` permission.

## Reuse after hard delete

- Slug: a deleted Game's slug can be reused by a new Game.
- Steam identity: deleting a local Steam Game removes its
  `(source_type, external_id)` row, so the same App ID can be imported
  again later.  No tombstone/blocked-App-ID state exists.

## No-network guarantee

Deletion never instantiates `SteamClient`, `SteamImportFoundation`,
`SteamGameImportService`, or `SteamGameRefreshService`.

## Deletion vs archive

```text
archive (listing_status=archived)  → reversible, editorial/publication state
delete                              → permanent local record removal
```

These are intentionally distinct.
