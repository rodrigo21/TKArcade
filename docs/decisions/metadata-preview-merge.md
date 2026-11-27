# Metadata preview: pick values from both columns

Status: landed (2026-11-27).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The preview (`decisions/metadata-preview.md`) compared every answered
field in three columns, but only Tags and Age Ratings had a selection:
Tags opened a second picker for the provider names, and every other
field followed the fill-empty rule with one global **Replace existing
values** switch. A user could not keep one typed developer and take the
store's second one, drop a tag the game already carried, or pick the
provider date while keeping the typed developer. The merge landed for
tags and ratings (`decisions/metadata-merge.md`), but the surface was
two separate selection models and a switch whose meaning changed with
the field.

## Decision

1. Every preview row becomes a field block with **Current** and **New**
   columns:
   - List fields (`tags`, `age_ratings`, `developer`, `publisher`,
     `genre`) carry one checkbox per value on each side.
   - Scalar fields (`description`, `series`, `date`) carry one
     exclusive checkbox pair; checking one side clears the other.
2. Defaults preserve the old fill-empty rule: list values start checked
   on both sides, a scalar starts on Current when it has a value and on
   New when it is empty.
3. Apply writes exactly the checked selection. For a list: the checked
   Current values first, then the checked New ones, deduped
   case-insensitively (the first spelling wins). A list with everything
   cleared writes nothing, like the all-declined tag picker before it.
4. A column header carries one checkbox per side and checks or clears
   every list value of that column. The boxes start unchecked and act on
   the column (first click checks it, the next clears it); they do not
   mirror the item states, which stay checked by default. The New header
   names the provider ("New (Steam)"). Scalars keep their per-field pair.
5. **Replace existing values** is removed: clearing the Current column
   is the replace, and the preview no longer needs a switch whose
   meaning depended on the field.
6. The preview's Tags picker is removed; the row is its own checkable
   list, seeded with the game's tags and the provider names. The Details
   tag picker (add tags, manage the store) stays.
7. Age ratings keep one value per board: checking a value drops the
   same-board entry on the other side, at row creation and on every
   toggle; an unknown label counts as its own board.
8. `developer`, `publisher` and `genre` become lists on the preview
   surface. A value splits on `;` and, when there is no `;`, on `,`
   (older comma-joined data); Apply joins with `"; "`. The provider
   adapters (`storemeta`, `vndb`, `igdb`) also join these fields with
   `"; "`, so fresh answers read back without ambiguity.
9. Locks win as before: a locked row disables its boxes and Apply skips
   it. Bulk Download Metadata is unchanged: it fills empty fields, with
   no preview per field.
10. **Reset** in the footer clears the preview rows, the status line, the
    title candidates and the two header boxes, leaving the fields, the
    identities, the source, the query and the release list alone.
11. The Search Data window opens half of the work area's width and its
    whole height, so the two value columns and long lists have room.
    Lists render in full: one scroll covers the whole preview, with no
    capped scroll per column. The value columns start at the top, so a
    short side never centers against a long one.
12. A provider value the game already carries is marked `existing` in the
    New column: struck through, dimmer and unchecked by default, so the
    Current copy keeps it. This covers every field: list names compare
    case-insensitively and scalar texts compare trimmed and exact; Apply
    still dedupes the two spellings.
13. The description renders as a read-only six-line text box with its own
    scroll on both sides, like the Information tab; the other scalars stay
    one elided line. Clicking a scalar value (the text, not only the box)
    selects that side.

## Rationale

- Playnite's comparison answers the real question per field ("what do I
  keep?") instead of per field type; two columns with one checkbox per
  value express both the keep and the take case.
- Reusing the current default for scalars keeps the fill-empty promise:
  a value the user typed is never overwritten without a click.
- Checking the provider date while keeping a typed developer is only
  possible if every field carries its own choice; a switch cannot.
- `;` separates names that can carry commas, and splitting a comma-only
  value keeps configurations written before this change readable.
- One board per rating stays a hard rule: a union would let PEGI 12 and
  PEGI 18 describe the same game.

## Consequences

- The preview is taller: one block per field, every list value inline,
  and the window's single scroll reaches the top of the answer again.
- A clear of every box means "write nothing", not "clear the field"; the
  field editors on Details remain the way to empty a value.
- The stored separator for developer/publisher/genre changes to `; ` on
  the next write. Older `, ` values stay valid and split correctly until
  rewritten.
- Rows hold mutable check state: a single toggle writes in place (a
  rebuild would destroy the checkbox handling the click), while the
  column header and rating board changes rebuild the rows.
- The QML cases drive the checkboxes through their `clicked` signal, not
  a synthetic mouse hit: the preview scrolls and an offscreen click can
  land on the dialog footer.

## Alternatives

- **Keep the Replace switch and add checkboxes only to lists.** Two
  overlapping selection models; the switch would still not say which
  scalar wins.
- **One checkbox per field, current versus new.** Simpler, but a field
  with three provider names and two typed ones could not keep the mix.
- **Widen the real configuration format for these fields.** A list in
  the TOML would be a migration and a config break; the `;`-joined
  string keeps the format and the editors unchanged.
- **Split on `,` only.** Breaks on names that contain a comma, which is
  the reason for the `;` convention.
