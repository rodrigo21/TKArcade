# ProtonDB for local games

Status: landed (2026-11-10).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

ProtonDB only knows Steam AppIDs, so every ProtonDB surface was gated on
`steam.steam_appid(gameid)`: the table tier column, the Details badge,
the context menu item and the background refresh. A local game that also
exists on Steam showed no rating, and the only Steam AppID a local game
could hold was `[artwork] artwork_appid`, which is art-only: pointing it
at a different edition for a better cover would have silently borrowed
that edition's rating.

## Decision

1. A local game may store its own Steam store link in `[metadata]
   steam_appid` (digits only, empty when it has none). A `steam-*` ID
   derives its AppID as before and ignores the field. This is the one
   documented exception to "external store IDs are never stored twice":
   a `local-*` ID carries no store identity to derive from.
2. One resolver decides the numeric target: the game's own Steam AppID,
   then the dialog draft, then the stored link. The Artwork Source AppID
   is never consulted.
3. The cache stays keyed by the canonical game ID
   (`protondb/local-doom.json`), so the Removed games cleanup finds it
   and the numeric-name cache migration leaves it alone. The payload
   records the AppID it was fetched for; a payload whose target differs
   reads as not cached, so changing the link never shows the previous
   game's tier. Payloads written before this change carry no target and
   stay valid.
4. The table column, the Details rating, the context menu item and the
   background refresh use the resolver. The Details tab shows a Steam
   AppID field above the rating, for local games only; the unsaved text
   drives the badge and the page link before Save, and saving a changed
   link triggers the same background lookup as a first save.

## Consequences

- A local game without a link behaves exactly as before: no tier, no
  menu item, `[metadata] steam_appid` absent.
- Two local games pointing at the same Steam AppID keep two cache files
  (same data, one request each per 30-day TTL).
- Clearing or changing the link leaves the old cache file on disk; it is
  ignored and goes away with the Removed games cleanup.
- The release date column still fills only for Steam IDs: a local game
  keeps the manual `[metadata] date`. A future metadata provider can
  reuse the same link.

## Alternatives

- **Reuse `[artwork] artwork_appid`.** Zero new config, but the field
  means "whose artwork this game borrows"; a different edition for art
  would change the rating too.
- **Cache under the numeric AppID.** Shares one file with the real Steam
  game, but the Removed games cleanup would either leave it or delete a
  live game's cache.
- **Derive the AppID from `shortcuts.vdf`.** Only works for a local game
  already added to Steam, needs a VDF read on the list path, and cannot
  represent a game the user never added.
- **A `[store]` section or a `store_appid` key.** One field does not
  need a section, and `steam_appid` names the store it links to.
