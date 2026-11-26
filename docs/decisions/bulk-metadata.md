# Batch Download Metadata

Status: landed (2026-11-26).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`decisions/online-tags.md` closed the online-tags theme with one open
question for the maintainer: whether the sidebar categories should
derive from tags and whether a bulk download is worth it. Tags stayed
out of the sidebar (manual categories are the curated, icon-bearing
taxonomy), and the library import brought a real library in: hundreds
of Lutris entries, most of them with a Steam identity, that would need
a Download Metadata and a Save per game. The single-game window is a
reviewed write by design (`decisions/metadata-preview.md`), so a batch
cannot reuse it verbatim.

## Decision

1. **The sidebar stays manual.** Tags never derive categories, icons or
   sidebar rows. The tag filter beside the search field remains the tag
   navigation, and `[general] categories` remains the taxonomy
   (`decisions/categories.md`).
2. **The selection is the source.** `Download Metadata…` in the
   selection menu opens the batch for the current `selectedIds`, like
   Set Categories and Set Tags: no new selector, and a filter or
   `Ctrl+A` scopes the batch. An empty selection answers
   `Select Games First.` and opens nothing.
3. **The batch lists every selected game.** One row per game in the
   selection order, with its match, provider and the fields it would
   fill. Rows resolve in a background worker, one signal per resolved
   row, and the list stays usable while it runs.
4. **Match resolution.** A stored identity wins: `vndb_id`, then
   `igdb_id`, then a Steam library id or `[metadata] steam_appid`.
   Without one, the game is searched by title in the **source** picked
   in the window: IGDB when its Twitch credentials exist, else Steam,
   with VNDB available. A searched row is checked by default only when
   the candidate title is the game's own (case, accents and punctuation
   ignored; a provider label that adds a release year still counts).
   Anything else stays checked off until the user looks at the name.
5. **The worker never writes.** It reads configs and providers, so
   Apply can run while the rest of the list still resolves; Apply stops
   the worker first and writes only the rows checked at that moment.
6. **Apply is fill-empty, and only fill-empty.** A locked field stays
   out even when empty. Tags and age ratings are written only when the
   game has none: the merge policy of `decisions/metadata-merge.md`
   needs a preview of the merged result, which a batch does not show.
   There is no Replace switch.
7. **A searched match stores its identity** on Apply
   (`steam_appid`/`vndb_id`/`igdb_id`), so the next run reuses it
   instead of searching again. For a local game the Steam link is also
   the ProtonDB target; its tier fills on the next open rather than in
   the batch.
8. **One game at a time, gated and cancellable.** The worker is a
   single thread and each provider call passes the registry's rate gate
   (`decisions/metadata-provider.md`); Cancel stops between games. A
   failed load, save or provider call counts in the summary and leaves
   that config alone. No artwork and no ProtonDB fetch run in a batch.
9. `DialogWindow` gained `acceptEnabled`, so a dialog can keep its
   accept button visible and disabled until the body has a checked row.

## Consequences

- A large selection takes minutes: the gates allow one VNDB call per
  second and four IGDB calls per second. The list shows progress and can
  be stopped with the resolved rows applied.
- A searched near-match is one look away from a wrong identity; the row
  shows the candidate name and is not checked by default.
- A tag list filled by a batch has the provider's vocabulary only for
  games that had none; a game with tags keeps them until a single-game
  download with Replace.
- The batch offers no per-row edit: fixing a match means the game's
  Search Data window, which stores the identity for the next batch.
