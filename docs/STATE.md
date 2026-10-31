# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  packaging churn in `packaging/arch/tkarcade-git/` (`PKGBUILD`
  `pkgver` and an untracked `.SRCINFO`, never committed); `.qoder/` is
  git-ignored.
- Landed: the categories redesign, squashed into one commit. Categories
  work like Lutris's: a Categories section in the library sidebar
  (Origins sources above with icons, `Edit Categories` framed by
  separator lines) replaces the `CategoryDialog` filter; assignment is
  the checkable Set Categories list with tri-state and a new-tag field;
  categories live in `categories.toml` with an icon and a manager/editor;
  tags normalize case-insensitively; `TKARCADE_OPEN=category` expands
  the sidebar. Resized dialogs now grow their capped lists and text
  areas.
- Before it: the profile selector `display` text-role fix, and the
  landing gate itself.
- Verified: `scripts/check.sh --qml` 485 passed (one benign isolated
  rerun), the category/settings cases in isolation, and offscreen
  screenshots (sidebar expanded at default and minimum width, manager,
  editor, picker, resized dialogs; zero engine warnings). Venv refreshed
  after the merge.
- Next: re-enter plan mode for the next theme. `TODO.md` holds the
  deferred DXVK, external-runtime, Preferences and Global Defaults design
  reviews and the release pass (only when the maintainer opens it).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
