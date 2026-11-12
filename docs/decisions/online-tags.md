# Online tags

Status: landed (2026-11-12).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

C8 of `docs/plans/metadata-provider.md` was the last consumer of the
metadata registry: online sources for categories/tags à la Playnite.
The per-game categories and the drawer filter already shipped without
online data, and the maintainer chose to keep categories manual for now:
the taxonomy UX waits until the library import is in, so the providers
must not write `[general] categories`. The online data needed a home that
does not disturb the sidebar, the category store or the manual metadata
fields.

## Decision

1. `[metadata] tags` is a list of strings: the online taxonomy of the
   last Download Metadata. It is distinct from `[metadata] tag` (the
   free-form state label shown as `Name (TAG)`) and from
   `[general] categories` (the manual, sidebar taxonomy). Values are
   trimmed and deduped case-insensitively by `normalize_categories`.
2. The providers append a `tags` list to their payload, so the existing
   per-provider cache stores it with the rest:
   - Steam: genres, store categories (features such as `Single-player`)
     and the franchise.
   - IGDB: genres, franchises, themes and keywords; `FETCH_FIELDS` gained
     `themes.name,keywords.name`.
   - VNDB: tags with spoiler 0 and rating at least 2.0, strongest first,
     capped at 20 (`TAG_MIN_RATING`, `TAG_LIMIT`).

   The cache payload carries `CACHE_VERSION = 2`, so a fresh entry
   written before the tags field existed reads as cold and refetches
   instead of answering with a payload that cannot carry them.
3. Download Metadata is the only path: the single-game preview gained a
   Tags row next to the metadata fields, Apply fills the list and Save
   persists it. The fill-empty rule, the Replace switch and the per-field
   locks work as for any other row; tags have no lock entry.
4. `_apply_metadata()` writes the list only when the form map carries the
   `tags` key, so an older caller without the field never clears it.
5. Tags stay out of the sidebar filter, the category store,
   `metadata.FIELDS` and `LOCKABLE_FIELDS`. Details shows the list
   read-only next to Series, from the `loadGame()` map.
6. Deriving categories from tags, or editing the list by hand, stays open
   until the maintainer reviews the result after the library import; the
   field exists so that decision needs no new download.

## Consequences

- One game at a time: there is no bulk tag action, so a large library
  needs a Download Metadata and a Save per game.
- A game without a Steam, VNDB or IGDB identity needs one manual field
  before the download can answer.
- The tag vocabulary belongs to the provider: switching the source on a
  later download replaces the old list.
