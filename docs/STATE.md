# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `fix/prefix-actions`, cut from `main` (`c65cadf`) with seven
  commits (four code, three docs), **not pushed, awaiting review**; `main`
  is untouched. The only uncommitted file is the maintainer's `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD` (left out of the commits on
  purpose). The venv was refreshed from the branch tip.
- Runtime tab, button geometry (two commits, the maintainer's call on
  both): `runtimeButtonWidth` (`gridUnit * 6` = 108 px) on every action
  except `settingsGfxRemove` — its label needs 121 px, so it stays at its
  own width instead of eliding; the Debug `Open` is `ptLogOpen` now and
  joined the column. The prefix hint label no longer hides itself when
  empty, so a Steam game's `Clear…`/`Open` end at the frame edge like the
  rest. Offscreen check at 756/612 px: 108 × 25 everywhere, right edges
  equal (736/592, 8 px inside the frame), 0 QML warnings.
- Trade-off to keep in mind at the 612 px minimum: the two 108 px buttons
  leave the local hint 184 px, so it wraps to 5 lines (it took ~3 with the
  old 80 px floor); the row is just as tall as its text, no blank filler.
  If that ever reads badly, the lever is the hint's own minimum or moving
  `Clear…`/`Open` under the row.
- Landed on the branch: the Runtime tab's prefix row, finished and fixed.
  - `Clear…`/`Open` now follow the prefix **on disk** (`prefixExists`,
    set in `refreshPrefixHint()` from `prefixNameState().exists`), not the
    field text: a local game using the default base had a prefix and no
    way to open or delete it, while a typed base whose folder is created
    at launch showed both buttons and failed. Steam keeps its old rule
    (non-empty `[runtime] prefix`).
  - Both prefix fields carry their value in the tooltip: QQC2 scrolls a
    long value without an ellipsis.
  - The base/folder row, the inline pickers, the per-game base for
    `prefixChoices` and the translations (605 finished, pt_BR included)
    were already in the tree uncommitted; they went in with the above.
  - The QML case pins the new rule (existing prefix → buttons, absent →
    none) and the model case the per-game base.
- Tried and **reverted**: `twinFormLayouts` on the Runtime tab's four
  forms to give them one label column. With `WidgetsFormLayout`'s
  `implicitWidth: width` the shared column inflates (offscreen: a Prefix
  field went 133 → 210 px, `DXVK:` 78 px right of `Runtime:`), so the
  8 px gap between sections stays. Recorded in `docs/QML-NOTES.md`; the
  fix needs an explicit per-tab label width (`TODO.md`).
- Verified on the branch: `scripts/check.sh` → 470 passed;
  `TKARCADE_QML_WORKERS=1 pytest tests/test_kirigami_qml.py` → 1 passed
  (the plain `--qml` run segfaulted in the driver process, twice-known
  Qt 6.12 teardown flake — serial is the documented remedy); ruff
  check/format clean. Offscreen screenshots at 756/612 px, both game
  kinds: buttons inside the frame and aligned with the hint row, tooltips
  end with the value, and with `/usr/share/icons` in the theme path both
  inline-action glyphs paint with the text clear of them (the blank
  glyphs in the earlier check were a missing offscreen theme, not code).
- Integration once approved: `git merge --squash fix/prefix-actions` on
  `main`, one commit, then `git branch -D` and push.
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
