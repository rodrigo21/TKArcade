# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `feature/drop-category-column`, one commit off `main`
  (c9f5473), not pushed or merged; `main` is untouched until the change
  is approved. The maintainer's uncommitted `pkgver` in
  `packaging/arch/tkarcade-git/PKGBUILD` is still outside the commit.
  The venv was refreshed after the last change.
- On the branch: the library list dropped its Category column (a
  comma-joined tag list next to the shaped columns read poorly).
  - `GameFilterModel` now has 11 view columns (`TABLE_COLUMNS` 0..10);
    `_DEFAULT_HIDDEN` is `{7, 8, 9, 10}`; order/width validation and
    the `showCategory` flag/property are gone. A stored 12-slot
    `column_order` fails validation and resets to the default layout
    (`_load_columns`' existing no-shim rule).
  - `MainPage.qml`: column visibility/sort/title/docs entries, the
    `cellText` list and tooltip and the "Show Category" header-menu
    item removed; `ColumnsDialog.qml` lost the row and the `[2..10]`
    model shrank. `GameListModel` keeps 12 internal source columns:
    `CategoryRole` still feeds the drawer filter.
  - Untouched: the Game tab's categories field, bulk "Set
    Categories…", the drawer filter and `CategoryDialog`.
  - `scripts/refresh-translations.sh`: 602 messages, 3 obsolete entries
    dropped ("Category" ×2, "Show Category").
- Verified: `scripts/check.sh --changed` widened to the whole fast suite
  plus the QML driver (model.py/QML touched) → 471 passed, only the
  known batch-abort re-run warnings. Offscreen shot 1600x900 with every
  column visible: 11 headers ending in Install Dir, no trailing empty
  slot, values aligned, no QML warnings. Details dialog opens; the
  popup itself does not show in `grabWindow`.
- Next: the maintainer tests the venv build and approves. Then
  `git merge --squash feature/drop-category-column`, one commit,
  `git branch -D` + `git push origin --delete`, and refresh the venv
  again after the merge.
- After that: the views beyond the list (icons and cards) — the Cover
  slot still has no consumer; read `docs/QML-NOTES.md` first. Then the
  artwork leftovers and the game taxonomy decision.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
