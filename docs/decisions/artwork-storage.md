# Artwork storage: Qt-decoded imports, one stored format

Status: landed (2026-11-15).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

Artwork import trusted a fixed list of signatures (PNG, JPEG, WebP), so
a valid image in any other format was refused: f95zone, for one, serves
AVIF whatever the URL extension says, and the dialog answered "That URL
Is Not an Image." Provider downloads kept the format the CDN sent
(often multi-MB PNGs), and the manual slot had no way to reuse the icon
of the `.exe` a native port ships beside its `.sh`.

## Decision

- The GUI decodes every imported image with `QImageReader` and its
  installed plugins, so the accepted formats are whatever the machine
  can read. SVG, AVIF, JPEG XL, HEIF, TIFF, PSD, ICO and the rest are
  inputs; the core `artwork` module keeps no format list beyond the
  ones it writes.
- The app writes artwork in one format, chosen in Preferences →
  Artwork → **Stored Images** (`[ui] artwork_format`, `artwork_quality`):
  `auto` (default) is AVIF at the configured quality (85), falling back
  to WebP at 90, JPEG at 90 and PNG, picking the first format the Qt
  plugins can write. An explicit lossy choice uses the quality slider.
- JPEG has no alpha channel, so an `icon` never stores as JPEG; it takes
  the PNG fallback. Losing transparency would put a black box on the
  list.
- Pocket size limits: above 4096 px on the longest side the image is
  stored with a warning; the hard limit is 8192 px on any side or
  33 554 432 pixels total, refused before it is decoded (a small file
  can decode into hundreds of MB).
- A picked `.exe` stores the largest frame of its embedded icon
  (`icoextract`, then Qt). A local game whose executable is not a `.exe`
  uses the same-stem `.exe` beside it, or the only `.exe` in that folder
  when there is one; several candidates and no match mean no icon.
  The icon extracted automatically keeps the best frame too: a PNG frame
  is written as `<key>-exe.png`, a BMP-only icon as `<key>-exe.ico` with
  its directory sorted largest first, because Qt otherwise reads the
  16x16 frame. A version marker in the sidecar re-extracts icons cached
  before that rule. The icon is extraction-time PNG/ICO only because the
  extraction is stdlib; the background pass and **Re-encode Existing
  Artwork…** rewrite it in the stored format (AVIF by default), record
  the new suffix in the sidecar and leave no generated image outside the
  format.
- A stored `icon` is downscaled to 1024 px on its longest side (aspect
  and alpha kept): the dialog's tooltip zooms to about 378 logical px
  and the card fallback to about 324, so 1024 covers a 2x screen and
  nothing bigger can be seen. Covers, banners and backgrounds keep
  their size, within the pixel limits below. The re-encode pass applies
  the cap to an oversized icon even when it already has the target
  format.
- For a local game, the icon the executable ships beats Steam's
  official art, whether it comes from the game's cache or from the
  Artwork Source AppID: official client icons are 32x32 and a donor's
  cover used as an icon is worse than the real icon. Manual slots and
  community icons still win. A fetch sees a 32x32 official icon
  (provider `steam`, below 128 px) and tries SteamGridDB for the icon
  when a key exists, overwriting only on success; the first background
  pass does the same for icons cached before this rule, once, guarded by
  `grids/.icon-upgrade-v1`.
- Downloads from a provider are re-encoded after the fetch, the manual
  slot on import, and **Re-encode Existing Artwork…** rewrites the whole
  cache and every manual slot in one pass, updating the `[artwork]`
  paths in the game configs. A file already in the target format is
  skipped, so a second run never stacks another lossy pass. The
  originals are replaced; the confirmation says so.
- The Arch package keeps the extra format plugins in `optdepends`
  (`qt6-imageformats` for WebP/TIFF, `kimageformats` for AVIF/JPEG XL/
  HEIF and more): the default install writes and reads PNG, JPEG and
  GIF, and `auto` falls back accordingly.

## Consequences

- A machine without `kimageformats` still imports any base-Qt format
  and stores JPEG or PNG. Removing the plugin after storing AVIF leaves
  those tiles unreadable; the format setting is the remedy.
- Re-encoding is lossy and one-way. Manual images can be picked again;
  downloaded art comes back with Fetch Artwork. Profiles keep their old
  `[artwork]` path, which is cosmetic: resolution reads the manual slot,
  not the stored path.
- The launch path still imports no Qt: decoding lives in
  `gui/artwork_io.py`, and the stdlib `artwork` module only gained AVIF
  signature detection, the size limits and the executable lookup.
