# Library background display

Status: landed (2026-11-25).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`artwork-background.md` stored a fourth artwork kind and left nothing
drawing it: "A later change (dialog backdrop, page header) consumes it".
The library had no use for the wide art, and the game list already drew
covers and banners. The maintainer asked for two optional consumers, a
backdrop behind the games and a preview on hover, and accepted both as
independent preferences.

## Decision

1. The selected game's wide art can sit behind every library view
   (`list`, `icons`, `cards`) as a dimmed backdrop.
2. A delayed tooltip can show the same art while the pointer rests on a
   game (card, icon cell, or the name cell of a list row).
3. Both are off by default and independent: `[ui] library_backdrop` and
   `[ui] background_preview`, in Preferences → Interface.
4. The source is `artworkPreview(id, "background")`: the game's manual
   background, then its cached background, then the banner chain, so a
   game with only a banner still shows art. No provider downloads
   anything new (`artwork-background.md`).
5. The backdrop follows the primary selection (`selectedIds[0]`), not
   the pointer; no selection or no art draws nothing. It reloads when a
   stored artwork changes.
6. The backdrop is dimmed by the theme's background color, and the
   picture's share is the **Visibility** slider (10–60%, default 30%,
   `[ui] backdrop_visibility`; the dim is drawn as `1 - value`). There is
   no blur. The tooltip caps its picture at 27 grid units wide and loads
   only while shown.
   - Superseded in part 2026-11-27: the backdrop now puts a blurred,
     cropped copy of the art behind the sharp aspect-fit picture; see
     `decisions/background-fit.md`. The tooltip keeps no blur.
7. `[ui] backdrop_bold` (off by default) switches the text drawn over
   the art to a heavier font: the table name, text and played cells,
   the card footer and the icon played line. Headers, gutters, the
   ProtonDB badge and the icon names keep their own weight.
8. The tooltip carries the game name above the picture, so the bubble
   is never empty (`docs/QML-NOTES.md`) and the art has a label.

## Rationale

- The backdrop is keyboard-visible: it follows selection, so a
  keyboard user sees the same art without a pointer. The hover tooltip
  is pointer-only and complements it rather than replacing it.
- One image behind the views costs one decode per selection, not one
  per card. The hover tooltip loads on demand and unloads on exit.
- The background kind already exists and falls back to the banner;
  consuming it adds no new storage, key or download.
- Both settings ship because the maintainer asked for both; each is a
  one-line switch, and neither changes the other's rendering.
- Bold is a metric-only aid: it darkens the glyphs without a color or a
  shadow, and the fixed column widths simply elide earlier instead of
  reflowing the table.

## Consequences

- A busy bright backdrop can fight the theme text; the Visibility
  slider bounds the picture at 60% and defaults to 30%, so the default
  look stays readable and the user can strengthen the art without a
  code change.
- `artwork-background.md`'s "nothing draws it yet" is historical: the
  kind now has two consumers.
- In the list view the backdrop shows around the opaque header and
  gutter strips; the table rows themselves stay transparent.
- A hover preview is unreachable by keyboard and absent on touch.

## Alternatives

- **Hover preview only.** Cheaper per interaction, but invisible to a
  keyboard and it disappears when the pointer moves.
- **Backdrop only.** Simplest, but the maintainer wanted the peek
  without selecting a game.
- **Blur the backdrop.** Needs a shader effect and GPU work on every
  selection; the theme dim keeps contrast for far less code.
- **Follow the hovered game in the backdrop.** Two consumers would
  fight over one image, and the backdrop would flicker while browsing.
