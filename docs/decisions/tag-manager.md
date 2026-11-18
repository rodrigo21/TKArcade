# Tag manager

Status: landed (2026-11-18).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`tags.toml` only grows. `refresh()` registers every tag a game uses, so
a misspelled or abandoned name stays on record even after the last game
drops it, and the picker lists every name forever. There is no way to
rename a tag across the library, merge two spellings, delete one or
drop the unused names. Deleting the store entry alone does not work:
the next refresh registers the name again from the game configs.

## Decision

1. One entry point in the tag picker's footer (`Manage Tags…`) and one
   in the top-bar tag filter popup. The dialog is a separate modal
   window like Edit Categories.
2. Rows are the global store names with their game counts, plus Rename
   and Delete per row and a `Prune Unused` action that is enabled only
   when a zero-count name exists.
3. Rename rewrites `[metadata] tags` in every config carrying the old
   name. The store's casing wins when the target already exists: the
   two names merge, and a game carrying both ends up with the target
   once.
4. Delete asks for confirmation naming the game count, then removes the
   name from the store and from every game. The confirmation is the
   guard: the action cannot be undone from the UI.
5. Prune drops only names no game carries. Every name still in use
   stays, because `refresh()` would register it again anyway.
6. The open settings dialog holds a draft of the game's tags. The
   manager emits the rename/delete, and the dialog maps them in the
   draft and in the picker's checks, so a later Save cannot write the
   old name back. Prune only reloads the picker rows.
7. Tags never enter the sidebar, the category store or the category
   icons. Merge policy for provider downloads and bulk tag edits stay
   out of this record.
8. The dialog width follows its longest row up to half the screen; the
   list grows to 24 grid units and the window opens at least 18 grid
   units tall, so a large store scrolls less and a long name is not
   elided until it passes the cap.

## Consequences

- A rename or delete touches every config. A config that fails to save
  keeps the old name, and the next refresh registers it again in the
  store; the manager reports the count it did change, and the log
  carries the failure.
- The manager is store-wide and destructive. It is reachable only from
  the tag UI, never from the sidebar.
- Zero-count names remain visible until pruned, so a tag outlives the
  last game that used it, matching `categories.toml`.
