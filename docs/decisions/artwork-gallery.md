# Artwork chooser

Status: landed (2026-11-27).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Fetch Artwork picked each image automatically: the first official Steam
file that existed, the first SteamGridDB row after shape/style/score
sorting, the first IGDB artwork, or VNDB's least flagged screenshot. A
source can offer many good options (VNDB screenshots, SteamGridDB grids,
IGDB artworks) and the automatic row is not always the one the user
wants. The identity picker answered a different question: which game the
source describes.

## Decision

1. The manual Fetch Artwork opens the chooser instead of downloading.
   The background fill that runs on open or save stays automatic and
   silent; only the button waits for a pick.
2. The chooser shows the effective source's candidates per kind. Steam
   serves icon, cover and banner; SteamGridDB serves the three; IGDB and
   VNDB serve cover and banner and leave the icon to the chain.
3. The row that the old fetch would have picked is marked **Automatic**
   and starts selected. Every offered kind keeps one selected row, so a
   confirm never leaves an offered kind to chance.
4. Steam official candidates keep `fetch_official`'s file order and are
   probed with `HEAD` first: a 404 row is hidden, and the first existing
   file is the automatic pick. Each row carries its official name
   (Library Cover, Library Hero, Client Icon…). A local game with no
   Steam AppID, or a Steam game with no official asset, falls to
   SteamGridDB like the fetch chain does.
5. SteamGridDB lists the three kinds, sorted exactly like the automatic
   pick; IGDB lists the cover and every artwork followed by every
   screenshot, 16:9. VNDB lists the cover and every screenshot, least
   flagged first. Every list is capped at `GALLERY_LIMIT` (60) per kind
   and follows `[ui] hide_explicit_artwork` where the provider carries
   flags.
6. Previews load from provider URLs and never touch the artwork cache.
   IGDB asks a smaller CDN token (`t_cover_big`, `t_screenshot_med`)
   while the download keeps `t_720p`/`t_1080p`; VNDB has no thumbnail
   endpoint, so `sourceSize` caps the decode. SteamGridDB previews and
   downloads use the same `thumb` the automatic fetch stores.
7. A title search that cannot decide the game reuses the existing picker.
   The pick carries the id back into the chooser; the preview writes no
   identity. Confirm writes the resolved `[metadata] igdb_id`/`vndb_id`
   (never for an Artwork Source AppID), the SteamGridDB sidecar id, and
   only then downloads the chosen URLs into their kind slots.
8. After the picks, the normal chain fills the kinds the source did not
   offer when their slot is empty. It never replaces an offered kind,
   even when that kind's chosen download failed; the status reports the
   failure. The chosen icon also skips the weak-icon upgrade, so an
   explicit 32 px official icon is not replaced by a SteamGridDB one.
9. Cancel downloads nothing, writes nothing and restores the computed
   status line.

## Rationale

- The button is already the explicit action, so making it ask first
  needs no second control and keeps the automatic background fill
  untouched.
- A marked automatic row makes the default visible instead of implicit:
  the user can confirm blindly and still get the old result.
- Steam announcements and store pages have several official assets per
  game; a gallery is the only way to see which of them the CDN really
  serves.
- Filling only the kinds the source cannot serve keeps the promise that
  an offered kind uses the user's pick, while VNDB/IGDB still get a
  square icon from the chain.

## Rejected alternatives

- **A separate Choose Artwork button.** Two entry points would need a
  second explanation of the same candidates, and Fetch would keep
  overwriting first.
- **A per-tile picker.** Icons, covers and banners would each fetch the
  provider list separately, and the current automatic result would stay
  hidden.
- **A one-row-per-kind dialog with text labels only.** The point is
  judging the picture; names and dimensions alone do not show whether a
  screenshot is a character portrait or a menu.
- **Downloading every candidate into a temp cache.** It costs the full
  traffic twice and leaves files to clean; the provider thumbnail is
  enough to choose.
- **Writing the resolved identity on preview.** Cancelling the chooser
  would still change the game's metadata, so the write moved to the
  confirm.
