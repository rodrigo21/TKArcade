# Current state

Ambient instruction: `opencode.json` lists this file (and
`docs/README.md`, the document map) under `instructions`, so every
session reads them without being asked. Keep it short and factual —
history lives in `CHANGELOG.md` and git, deferred work in `TODO.md`,
document roles in `docs/README.md`. Refresh it with `/handoff` before
stopping mid-task.

- Branch: `confirm-dialogs-library`, two commits off `main`, not pushed
  or merged (awaiting approval). `main` is clean apart from the
  maintainer's `pkgver` churn in `packaging/arch/tkarcade-git/PKGBUILD`
  (never committed). `.qoder/` is git-ignored.
- First commit: the five library confirmations (`removeDialog`,
  `cleanupDialog`, `shaderDialog`, `overwriteDialog`, `resetDialog` in
  `MainPage.qml`) moved from `Kirigami.PromptDialog` popups to
  `ConfirmDialog.qml` windows. The component gained
  `default property alias extraContent` (the leftover checklist body)
  and `rejectText` ("Keep All"); objectNames lost the `settings` prefix
  (`confirmOk`, `confirmDetail`, ...) and `_confirm_window(qgui_app,
  name)` looks a dialog up by its own name. The tests read the cleanup
  checklist through `childItems()` (`_visual_item`), since Repeater
  delegates stay out of the QObject tree.
- Second commit: every remaining dialog is a separate modal `Window`
  too. `DialogWindow.qml` (input/report shape: body, OK + Cancel/Close,
  Enter on the accept button) now carries validate/clone/set-categories
  in `MainPage.qml`, all eight settings prompts (opened with
  `.open(gameSettings)`), and the `CategoryDialog`/`ColumnsDialog`
  roots; both history confirmations use `ConfirmDialog.qml`. No
  `Kirigami.Dialog` is left in the shell. The env bulk `TextArea` wraps
  anywhere (screenshot check: long `KEY=value` lines clipped).
- Verified: 480 fast tests, 481 with the QML driver (known unrelated
  batch-abort retries), and offscreen screenshots under
  `org.kde.desktop` of all 13 dialogs (titles, wrapping, button rows).
  Venv refreshed after the commits.
- Before it (on `main`): the settings confirmations became separate
  modal `Window`s (`ConfirmDialog.qml`, QMessageBox shape), and the
  per-game `[metadata]` fields with the `Name [version] (TAG)` suffix.
- Next: merge `confirm-dialogs-library` with `git merge --squash` once
  approved, then the open `TODO.md` items — the artwork leftovers
  (cover consumer, per-game provider override, "Artwork Cleared") and
  the categories details section.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
