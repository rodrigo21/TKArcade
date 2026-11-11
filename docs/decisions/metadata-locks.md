# Metadata field locks

Status: landed (2026-11-11).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The metadata preview before writing (C2) could replace typed values, and
the only protection was the all-or-nothing **Replace existing values**
switch: opting into one replacement opted every field into the
overwrite. A field the user wants to keep survived only by leaving the
switch off, which also blocked the replacements they wanted. A lock has
to survive downloads, so it belongs in the per-game config.

## Decision

1. `[metadata] locked` is a CSV of field names. `normalize_locked_fields`
   lowercases, drops unknown names, dedupes and writes the canonical
   `LOCKABLE_FIELDS` order; a TOML list is accepted and saved as CSV.
2. Lockable fields: description, developer, publisher, genre, series,
   age_ratings, region, status, tag, version and date. `steam_appid` is
   identity and categories are taxonomy, so neither takes a lock.
3. Every lockable row on the Details tab ends with an icon-only lock
   toggle (`LockButton.qml`, `objectName` `settingsLock<Field>`): a closed
   lock means locked, an open lock means unlocked, and the tooltip names
   the click. The state saves with the form; Cancel drops it. A profile
   carries its locks like every other config value.
4. Apply never writes a locked row: empty or typed, with the replace
   switch on or off. The lock wins over the switch. The preview shows
   `Locked` in the New cell instead of the provider answer.
5. A skipped locked row counts as kept in the landed status strings,
   which do not change.
6. Unknown names are dropped on load, so a typo cannot silently lock a
   field; nothing writes locks automatically.

## Rationale

- A per-game lock survives every download and matches its consumers: the
  same config already holds the values it protects.
- An icon-only toggle per row costs no placeholder text and shows the
  state at a glance, unlike a separate selection dialog.
- Gating in Apply keeps one writer and one undo path; the lock never
  touches the field text.

## Consequences

- Eleven rows carry one more control at the trailing edge.
- Locked rows never fill from a provider, even when empty; unlocking is
  the only way to let the store fill them.
- The set is wider than the seven provider fields: the import enrichment
  and online categories reuse the same rule.

## Alternatives

- **A locks dialog with checkboxes.** More clicks to reach the state and
  a second surface to keep in sync with the field list.
- **A toggle in the preview only.** It could not lock a field before the
  provider answers and would not cover the empty-field case.
- **A global lock list in Preferences.** Locks are per game, like the
  metadata they protect.
