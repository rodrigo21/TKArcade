# Artwork chooser: keep a kind and pick a background

Status: landed (2026-11-27).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The chooser preselected the automatic row of every offered kind, and
`apply()` fell back to the first row when a kind had no selection, so
every offered kind was always rewritten. Mixing sources lost the
previous pass: use Steam's art, open the chooser for VNDB and confirm,
and the Steam cover and banner were replaced.

The `background` kind had no candidate list in the chooser: only the
manual file picker or the banner fallback could fill it. A user asking
for a distinct wide backdrop had to download it somewhere else and pick
the file by hand.

## Decision

- Clicking the selected row again deselects that kind. The confirm sends
  the kind with an empty URL; the model records it as offered, so
  neither a candidate is downloaded nor the fallback chain fills it.
  Nothing is written or deleted: the art currently shown, whatever its
  source (our cache, Steam's library cache, the manual slot, the
  executable icon, the banner fallback), stays exactly as it is.
- The Download button requires at least one selected kind.
- The gallery derives a `background` group from the `banner` group for
  every provider, with `auto` cleared. The chooser does not preselect
  it. A per-section **Use the Banner** button selects the banner pick.
- `store_choice` accepts `background`, but `FETCH_KINDS` stays
  `("icon", "cover", "banner")`: the automatic and silent fetches still
  never download a background.
- A URL already stored for another kind is copied with
  `store_kind_copy` instead of downloaded twice, so duplicating the
  banner costs one local read.
- The previews grow: the dialog is 56 x 46 grid units, the cover cell
  9 x 13.5, the banner/background cell 20 x 9.3, and the icon keeps its
  4 x 4. IGDB previews ask for bigger CDN tokens (`t_cover_big_2x`,
  `t_screenshot_big`) while the download keeps `ART_SIZES`.

## Consequences

- A kind the source cannot serve at all (the IGDB/VNDB icon) is not in
  the chooser payload and still gets the chain fill when empty. A kind
  the user deselected never does.
- An explicit background stops following later banner changes. That is
  the difference between a copy and the empty-slot fallback.
- Confirming the chooser still releases a previous Clear of the game,
  as every explicit Fetch does; deselecting does not preserve that
  marker. Reverting it would change the "Clear hides everything until
  Fetch" rule and is a separate decision.
- No migration: old caches, manual slots and configs load unchanged.

## Alternatives

- **Preselecting a background row.** A blind confirm would write a
  second file for a picture already used as the banner and break the
  fallback without the user asking.
- **A checkbox keeping the background in sync with the banner.** It
  needs "linked until touched" state in QML and makes the selected
  border ambiguous. The explicit button is one line and one click.
- **Downloading the same URL twice.** Same bytes, extra request and a
  second decode; the copy is local.
- **Adding background to `FETCH_KINDS`.** Steam and SteamGridDB have no
  separate backdrop asset: the provider lists already serve the banner,
  and the silent fetch would duplicate every wide picture.
- **A separate Choose Artwork background button.** Two entry points
  would repeat the candidate list and the fallback explanation.
