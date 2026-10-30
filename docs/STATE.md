# Current state

Ambient instruction: `opencode.json` lists this file (and
`docs/README.md`, the document map) under `instructions`, so every
session reads them without being asked. Keep it short and factual —
history lives in `CHANGELOG.md` and git, deferred work in `TODO.md`,
document roles in `docs/README.md`. Refresh it with `/handoff` before
stopping mid-task.

- Branch: `main`, pushed and clean apart from the maintainer's
  `pkgver` churn in `packaging/arch/tkarcade-git/PKGBUILD` (never
  committed). `.qoder/` is git-ignored.
- Landed: the settings confirmations moved from `Kirigami.Dialog`
  popups to separate modal `Window`s (`ConfirmDialog.qml`, QMessageBox
  shape: left icon, right-aligned default button, height follows the
  content, a long detail in its own wrapping block). Tests reach it
  through `topLevelWindows()` (`_confirm_window`), never the settings
  item tree; the icon choice is a boolean so both theme fallbacks stay
  literal for the hicolor guard. The branch went in with
  `git merge --squash` (one commit) and was deleted; `TODO.md` records
  the five library confirmations (`removeDialog`, `cleanupDialog`,
  `shaderDialog`, `overwriteDialog`, `resetDialog` in `MainPage.qml`)
  that still use `Kirigami.PromptDialog`.
- Before it: per-game metadata — `[metadata] version`/`date`/`tag` with
  `split_name_version()`, `game_display_name()` and
  `metadata_date_valid()` in `config.py`; the library shows the
  `Name [version] (TAG)` suffix in every view (the saved name stays
  plain); a trailing `[x]` typed in the name moves into `version` on
  save; the Game tab gained the three fields and refuses a malformed
  release date.
- Verified: post-merge suite with the QML driver on `main` (481
  passed), and an offscreen screenshot check of the three dialog
  variants before the merge (it found one defect: the declared
  `minimumHeight` outweighed the content, so it was dropped). Venv
  refreshed after the merge.
- Next: the open `TODO.md` items — the five `MainPage` confirmations
  (promote `ConfirmDialog.qml` out of `GameSettings.qml`), the artwork
  leftovers (cover consumer, per-game provider override, "Artwork
  Cleared") and the categories details section.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
