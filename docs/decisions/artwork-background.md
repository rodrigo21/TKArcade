# Fourth artwork kind: background

Status: landed (2026-11-09).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Artwork had three kinds (`icon`, `cover`, `banner`). A wide backdrop for
the game page or dialog had no place of its own: the only wide art was
the banner, which the list and the cards already draw. Picking a
different wide image meant replacing the banner everywhere.

## Decision

A fourth kind, `background`, with its own manual slot, config key, cache
name and Artwork-tab preview. When it is empty it resolves to the banner
art, so nothing changes on screen until the user picks something.

- Config: `[artwork] background` (`ArtworkConfig.background`).
- Cache: `grids/<key>-background.<ext>`, apart from the cover's flat
  `<key>.png` and the banner's `<key>-banner.<ext>`.
- Resolution: the game's manual slot, then a cached background, then the
  same chain for `banner` (manual, cache, Steam's library cache), with
  the Artwork Source AppID handled the same way as the other kinds.
- Clear of `background` never touches the banner it fell back to.
- Providers download nothing for it: `FETCH_KINDS` stays
  `("icon", "cover", "banner")`, because SteamGridDB only serves grids,
  heroes, logos and icons, and the hero is already the banner. The
  preview names the provider of the banner it borrowed.
- Artwork tab: the preview strip runs icon, banner, background, cover,
  centered in the section outside the form's label column. A filled
  frame hugs the loaded picture plus an equal small margin on every side
  (an empty slot shows the kind's shape), so the art never touches the
  rounded corner. The backdrop begins as a copy of the banner, so both
  previews match while it has no art of its own, and only the tooltip
  tells them apart. The dialog's minimum width grew to 37 grid units to
  fit all four. Each
  tooltip names its kind at the top-left corner.

## Consequences

- No migration: existing caches and configs load unchanged, and the
  fallback keeps every game's current look.
- The kind is storage and a picker only; nothing draws it yet. A later
  change (dialog backdrop, page header) consumes it without touching the
  storage.
- A future fanart provider can add `background` to the fetch set.

## Alternatives

- **A `logo` kind.** Steam ships `logo.png` and SteamGridDB has
  `/logos`, so it would fit the providers, but a wide backdrop was the
  requested feature.
- **Re-point `banner` to card art and give the hero to `background`.**
  The Steam banner would lose resolution (`header.jpg`) and every cache
  would need a migration.
- **Download the hero twice, once per kind.** Same bytes, two files,
  no visual difference.
