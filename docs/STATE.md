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
- Verified: **nothing yet on the latest batch**. The QML case
  (`test_running_badge_updates_in_table`) gained asserts for
  `rowRunningFrame` and the Play/Stop text, and neither the fast suite nor
  the QML driver ran on it; the maintainer tested the visuals by hand.
  First task on the verify machine: that case, `scripts/check.sh
  --changed`, the full suite, then the driver. The previous batch held
  656 passed and 145 QML cases in 102s.
- Next: verify the landed batch (above). Then the fourth artwork kind
  (background/fanart, `TODO.md`); its arrival is when the preview sizes
  get revisited. Then the other game sources (Epic, GOG) with a
  per-source batch import, and the 1.0 packaging check (AppImage and
  recipes must ship `icoextract`/`pefile`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
