# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: thirty-three batches. The latest: the game dialog rework —
  Details and Execution tabs, Launch moved into Execution (still editable
  in Global Defaults), the profile-bar switch, manual `[metadata]`
  fields with the grouped age-ratings picker, status badges in the three
  views, and the ProtonDB row. The combo box popups now match the field
  width on every dialog. Before it: translations were suspended until
  1.0 (`tests/test_i18n.py` catalog tests are skipped), and the Wine
  column/Compat Tool work landed.
- Verified: the approved diff. 687 passed, 3 skipped with the QML driver
  (`scripts/check.sh --qml`); the dialog, status, age-picker and combo
  screenshots are in `/tmp/opencode/`.
- Next: the fourth artwork kind (background/fanart, `TODO.md`), then the
  other game sources (Epic, GOG). The 1.0 visual pass, the packaging
  check, the compatibility-shim removal and the release pass wait for
  the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
