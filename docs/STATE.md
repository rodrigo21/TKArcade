# Current state

Ambient instruction: `opencode.json` lists this file (and
`docs/README.md`, the document map) under `instructions`, so every
session reads them without being asked. Keep it short and factual —
history lives in `CHANGELOG.md` and git, deferred work in `TODO.md`,
document roles in `docs/README.md`. Refresh it with `/handoff` before
stopping mid-task.

- Branch: `main`, at the dialog-window merge (`74034c5`), pushed to
  `origin`. The `confirm-dialogs-library` branch was squash-merged and
  deleted. The working tree carries only the maintainer's `pkgver` churn
  in `packaging/arch/tkarcade-git/PKGBUILD` (never committed); `.qoder/`
  is git-ignored.
- Landed: every dialog in the shell is a separate modal `Window` now.
  The library confirmations (remove, leftover cleanup, shader cache,
  clone overwrite, reset) and the two history confirmations use
  `ConfirmDialog.qml` (`default property alias extraContent` for the
  leftover checklist, `rejectText` "Keep All", objectNames without the
  `settings` prefix). Inputs and reports use the new `DialogWindow.qml`
  (body, OK plus Cancel/Close, Enter on the accept button):
  validate/clone/set-categories in `MainPage.qml`, the category filter,
  Configure Columns and the eight settings prompts, opened with
  `.open(gameSettings)`. No `Kirigami.Dialog` is left in the shell. The
  env bulk `TextArea` wraps anywhere (long `KEY=value` lines clipped
  before). Tests reach dialogs via `_confirm_window(qgui_app, name)`;
  the cleanup checklist through `childItems()` (`_visual_item`), since
  Repeater delegates stay out of the QObject tree.
- Verified: 480 fast tests, 481 with the QML driver (known unrelated
  batch-abort retries), and offscreen screenshots under
  `org.kde.desktop` of all 13 dialogs (titles, wrapping, button rows).
  Venv refreshed after the merge and the handoff.
- Before it: the settings confirmations became separate modal `Window`s
  (`ConfirmDialog.qml`, QMessageBox shape), and the per-game
  `[metadata]` fields with the `Name [version] (TAG)` suffix.
- Next: the open `TODO.md` items — the artwork leftovers (cover
  consumer, per-game provider override, "Artwork Cleared") and the
  categories details section.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
