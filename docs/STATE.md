# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `main`, in sync with `origin/main` (the squash of
  `fix/prefix-actions`). The tree is clean apart from the maintainer's
  uncommitted `pkgver` in `packaging/arch/tkarcade-git/PKGBUILD`, left out
  of the landing on purpose. The venv was refreshed after the merge.
- Landed, one squash — the Runtime tab's prefix row, finished:
  - The prefix reads as the `<base>/<folder>` path the launch uses: base
    and folder on one labelled row with `(Base)`/`(Folder)` suffixes and
    each picker inline, which leaves room for `Clear…`/`Open` at the 612 px
    minimum. Steam keeps its single `Custom Prefix Dir:` field, and the
    existing-prefix list follows the base the game itself uses.
  - `Clear…`/`Open` follow the prefix **on disk** (`prefixExists`, from
    `prefixNameState().exists`), not the field text: a local game under the
    default base had a prefix and no way to reach it, while a base whose
    folder is created at launch showed both buttons and failed.
  - Long values land in the field tooltips (QQC2 scrolls without an
    ellipsis), and a Steam game's pair ends at the frame edge like the rest.
  - One width for the tab's actions (`runtimeButtonWidth`, `gridUnit * 6` =
    108 px, Debug `Open` included). `Remove from Prefix` keeps its 121 px
    because its label would elide; before, only
    `Winetricks…`/`Protontricks…` outgrew the style's 80 px floor.
- Tried and **reverted**: `twinFormLayouts` to share one label column
  across the tab's sections. With `WidgetsFormLayout`'s `implicitWidth:
  width` the column inflates (133 → 210 px offscreen, `DXVK:` 78 px right
  of `Runtime:`), so the 8 px gap between sections stays. The measurement
  and the "needs an explicit per-tab label width" conclusion live in
  `docs/QML-NOTES.md` and `TODO.md`.
- Verified: `scripts/check.sh --qml` → 471 passed before the squash and
  470 passed on `main` after it; ruff check/format clean; pt_BR catalog
  complete (605 finished). Offscreen screenshots at 756/612 px for Steam
  and local games: 108 × 25 actions with equal right edges, 0 QML
  warnings, and with `/usr/share/icons` in the theme path both
  inline-action glyphs paint (the blank glyphs of an earlier check were a
  missing offscreen theme, not code).
- Trade-off at the 612 px minimum: the two 108 px buttons leave the local
  game's hint 184 px, so it wraps to 5 lines (it took ~3 with the old
  80 px floor). The row is exactly as tall as its text. If that ever reads
  badly, move `Clear…`/`Open` under the hint at that width.
- Next concrete step: `TODO.md` in order — the per-tab label column, then
  the icons/cards views (the list is done), then the artwork leftovers
  (per-game provider override, "Artwork Cleared" in the Status row).
- Open decision: the game taxonomy (`TODO.md`, "Game taxonomy and
  terminology") — Origin/Platform/Runner names and what `[general]
  environment` becomes. It was deferred again; the `Commands` rename
  only settles the tab label, not the model.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533, and Steam expands
  `tkarcade %command%` through PATH (the dialog warns about it). The
  PKGBUILD already pins `#branch=main`.
- Nothing blocking.
