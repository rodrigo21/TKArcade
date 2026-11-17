# Manual tags

Status: landed (2026-11-17).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`docs/decisions/online-tags.md` made `[metadata] tags` a read-only list
of the last Download Metadata, shown next to Series with a Clear
button. A list longer than the row was invisible, the user could not
remove one provider tag without clearing every tag, and the same name
could not be reused on another game. Playnite treats tags as global
entities that a game picks from, and the maintainer asked for that
behaviour without moving tags into the sidebar.

## Decision

1. `[metadata] tags` is the game's tag list, editable on Details. It is
   still distinct from `[metadata] tag` (the free-form state label) and
   from `[general] categories` (the manual sidebar taxonomy). Values are
   trimmed and deduped case-insensitively by `normalize_categories`.
2. The Details row is a button that shows only the whole tags that fit,
   followed by a `+N` count; it never elides a tag and opens a checkable
   picker whose width follows the longest tag: two columns when they fit,
   one otherwise, capped at 60 grid units or 80% of the screen. Rows are
   the game's tags first, in their current
   order, then the global store alphabetically; a new-tag field creates
   names. OK updates the dialog draft and Save persists it, like Age
   Ratings. The read-only label and its Clear button are removed:
   unchecking every row clears the list.
3. A global `tags.toml` store holds every tag on record, with a
   `[tags] names` list. `refresh()` registers every tag in use, so a tag
   outlives the last game that carried it, the same rule as
   `categories.toml`. Unchecking a tag removes it from the game only.
   The store is packed by `export_configs()` and accepted by
   `import_configs()`.
4. Tags never enter the sidebar, the category store or the category
   icons. The library filters them from a tag button beside the search
   field: a popup lists the tags in use with their game counts, the
   selection is multi-valued, and every selected tag must match (AND).
   The tag filter combines with the existing text, source, issues and
   category filters by AND.
5. Download Metadata keeps the fill-empty/Replace rule and the tags
   lock. A game with a non-empty list keeps it unless Replace is on; a
   lock blocks the write even then. Providers do not merge into an
   existing list.
6. A tag is a user-owned name after it reaches the game: provenance
   (manual or provider) is not tracked, and the global store learns the
   provider vocabulary as it is used. The tag manager, merge policy,
   match-any mode, preview selection, bulk edits, column and persistent
   filter are follow-ups in `TODO.md`.

## Consequences

- A very large store needs the picker search and the manager that are
  still open; today the picker scrolls.
- Replace can overwrite manual edits, by explicit choice; the lock is
  the guard. A fully cleared list counts as empty, so a later fill-empty
  download can refill it unless the tags lock is on.
- Tags and categories with the same name stay independent.
- Above the width cap a single very long tag elides; it never wraps onto
  a second line.
