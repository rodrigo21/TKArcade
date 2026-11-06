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
- Landed: nineteen batches. The latest one: the running marker in the
  list view — a positive wash over the row plus a green outline from the
  row number to the end of the name (drawn above the icon, the name cell
  raised while it shows), and the toolbar Play turning into Stop with the
  game's name in the tooltip for the selected running game, through the
  same terminate path as the context menu. Before it: QML suite cost (no
  duplicated cases; the four source-only wiring checks moved to
  `tests/test_qml_static.py`, the driver batches 10 cases with up to four
  workers and recovers an aborted batch as a group, ~1:45 on four cores),
  QML suite isolation, and a Steam game's Runtime preselected from Steam's
  compat mapping.
- Verified: the latest batch, on the verify machine.
  `test_running_badge_updates_in_table` (the new `rowRunningFrame` and
  Play/Stop asserts) passed alone; the fast suite held 656 passed and the
  driver ran its 145 cases 657 passed in 64.69s with no aborted batch.
  `scripts/check.sh --changed` only reached `tests/test_packaging.py`,
  because the tree is clean against the commit that carries the batch and
  only the PKGBUILD is dirty, so the full suite and the driver are what
  covered it.
- Next: the fourth artwork kind (background/fanart, `TODO.md`); its
  arrival is when the preview sizes get revisited. Then the other game
  sources (Epic, GOG) with a per-source batch import, and the 1.0
  packaging check (AppImage and recipes must ship `icoextract`/`pefile`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
