# Metadata preview

Status: landed (2026-11-11).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The landed Download Metadata action wrote the store answer into the
dialog as soon as it arrived. Fill-empty-only kept typed fields safe,
but the user could not see what the store would change before it
changed: the answer appeared already applied, and cancelling was the
only way to undo it. The provider registry (`decisions/metadata-registry.md`)
made the field map a first-class answer, so the action could show it.

## Decision

1. Download Metadata opens a preview dialog (a `DialogWindow`, like the
   other settings dialogs): one row per field the provider answered,
   `Field | Current | New`, plus a **Replace existing values** switch off
   by default. Fields the provider answered empty get no row.
2. `Current` is read from the dialog controls, not from the saved
   config, so unsaved edits in the open dialog count. `New` is the
   provider answer; the age ratings show joined and apply as a list.
3. **Apply** is the only writer, and it writes the controls; Save still
   writes the config. Cancel and closing write nothing.
4. Apply fills empty fields only. With the switch on it replaces the
   typed values too; that switch is the explicit confirmation for an
   irreversible overwrite until the per-field locks land (C3).
5. The date is a preview row now that the Steam adapter answers it;
   only the value the adapter already normalized (ISO) is written.
6. The status line keeps its landed strings: `Metadata Loaded.`,
   `Loaded; Typed Fields Kept.`, `Nothing to Fill.` after Apply, and
   `No Metadata Found.` (no dialog) when the provider answered nothing.
7. No provider menu and no candidate picker yet: with Steam only there
   is nothing to choose and no ambiguous search. The menu joins C6 (the
   second provider) and the picker C4 (VNDB), like `search()` in the
   registry.

## Rationale

- The preview makes the overwrite visible before it happens, which is
  what fill-empty-only could not do on its own.
- Writing the controls keeps one config writer (Save) and one undo path
  (Cancel), exactly like the rest of the dialog.
- Rows for answered fields only keep the dialog short; Steam often
  answers no series and no date.

## Consequences

- Replacing a typed synopsis is irreversible until C3 adds the locks;
  the switch stays off by default.
- Long values are elided in the row and readable through a tooltip, so
  the dialog height follows the field count, not the text length.
- Nothing new is cached: the preview reads the same 30-day cache.

## Alternatives

- **Keep writing on arrival and show a report afterwards.** Undo would
  need another action, and the user never sees the change first.
- **Confirm dialog with one sentence.** Hides which fields would change,
  which is the point of the preview.
- **Per-field checkboxes now.** That is the C3 field-lock surface; a
  second selection model in C2 would duplicate it.
