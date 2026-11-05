# Executable icon for a local game

Status: decided (2026-11-05).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

A local Windows game has no Steam AppID, so until it downloads art it
shows a blank icon in the list, the cards and the dialog, even though the
game's own executable carries a proper icon in its resources.

## Decision

1. When a local game's icon slot is empty, the icon embedded in its
   `[general] custom_executable` fills it. The source comes back as
   `"exe"` from `artwork.resolve`.
2. It is the **last** step of the chain: manual slot, downloaded cache
   (icon, then cover), Steam's own art, then the executable. A Steam game
   never uses it, even with an executable override: Steam's icon is the
   one the client itself draws.
3. Extraction uses `icoextract` (pure Python, MIT, `pefile` underneath)
   instead of a parser of our own. Its import is lazy and any failure
   (missing package, no resources, malformed PE) means "no icon".
4. The `.ico` is written to the art cache as `grids/<key>-exe.ico`, a name
   the downloaded-icon resolver never looks at and `artwork.clear` never
   deletes. The sidecar key `exe_icon` records the source path, mtime and
   size, so a refresh only stats the executable and a changed one is
   re-extracted.
5. Qt reads the assembled `.ico` directly, so nothing is converted to PNG
   and no image library is involved.

## Rationale

- The executable icon costs no network call and needs no API key, which
  makes it the only art a fresh local game has without a lookup.
- Being last keeps every explicit choice above it: a fetched icon, the
  Artwork Source AppID or a hand-picked file all beat it.
- `icoextract` already assembles a valid multi-size `.ico` from the
  `RT_GROUP_ICON`/`RT_ICON` resources, which is the whole job; a local
  parser would reimplement it for no gain.
- Keeping the file out of `<key>-icon.*` means Clear (which drops
  downloaded art) leaves a game-shipped icon alone, and a download can
  still replace what the list shows without deleting the cache.

## Rejected alternatives

- **A parser of our own.** Same output, more code and a PE fixture for
  its test.
- **`icoutils` (`wrestool`/`icotool`) through subprocess.** Extra external
  tool with a multi-step recipe, and a runtime dependency on something
  not every distro ships.
- **Convert the frames to PNG with Qt.** Qt's ICO reader handles the
  assembled file; a conversion step would only add a GUI-only path.
- **Use the executable icon before Steam art.** A 32x32 game icon is not
  better than the official art the client already has.
