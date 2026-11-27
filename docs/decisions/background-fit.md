# Library backdrop fit

Status: landed (2026-11-27).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`background-display.md` drew the selected game's background with
`Image.PreserveAspectCrop` over the whole page. The stored background is
usually the 1920x620 Steam hero (3.1:1) and the page is near 1.5:1, so
cover-cropping threw away about half the picture's width.

## Decision

Two layers behind the views, both bound to the same
`artworkPreview(id, "background")` URL:

1. `libraryBackdropFill`: the same art with `PreserveAspectCrop` and
   `sourceSize.width: 512`, rendered behind a `MultiEffect` blur
   (`blurEnabled`, `blur: 0.8`, `blurMax: 64`). It fills the room around
   the sharp picture, so no theme-colored bands remain.
2. `libraryBackdrop`: the same art with `PreserveAspectFit`, sharp,
   centered and complete.

The existing dim rectangle sits after both; the Visibility slider keeps
its meaning and the two `[ui]` switches are unchanged. The hover tooltip
already used `PreserveAspectFit` and stays as it is.

`QtQuick.Effects` supplies `MultiEffect`; it ships with Qt 6 and needs no
new package. The blurred copy decodes 512 px wide, so the extra decode
and the shader work stay small; the effect only runs while the backdrop
is visible.

## Consequences

- `background-display.md`'s "There is no blur" is superseded for the
  backdrop. It still holds for the tooltip.
- The blur is GPU work on selection and resize; the sharp layer and the
  dim are unchanged.
- A page much wider than tall still shows the whole sharp picture: the
  room becomes blurred art instead of empty color.
- No storage, config key, download or migration changes.

## Alternatives

- **Fit only.** One-line change with theme-colored bands; rejected
  because a 3.1:1 hero leaves close to half the page flat.
- **Keep the crop.** Changing the crop anchor only moves the loss.
- **Blur the whole backdrop, no sharp copy.** Removes the crop but
  loses the art's detail.
- **Stretch the art.** No crop and no bands, but a 3.1:1 picture in a
  1.5:1 page is visibly distorted even under the dim.
- **A `[ui]` switch between fit and fill.** Two visual modes to explain
  for one preference the maintainer asked to improve.
