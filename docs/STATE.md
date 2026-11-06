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
- Landed: eighteen batches. The latest one: QML suite cost — an audit
  found no duplicated cases; the four source-only wiring checks moved to
  `tests/test_qml_static.py` (fast suite) and the Preferences Enter case
  folded into the save roundtrip (145 QML cases), the driver batches 10
  cases with up to four workers and recovers an aborted batch as a group,
  isolating only the crasher (2–2.5 min to ~1:45 on four cores). Before
  it: QML suite isolation (nothing wraps a `Controls.Menu` in Python; the
  shell's Escape filter reads the popup's `QQuickPopupItem`), and a Steam
  game's Runtime preselected from Steam's compat mapping. Earlier: the
  ProtonDB tier, release date and artwork fetch for a newly added game,
  the executable icon for local games (`icoextract`), the Artwork tab
  previews, and the test policy (full suite once per approval round).
- Verified: `scripts/check.sh` 656 passed and the QML driver 145 cases in
  102s on that diff; venv refreshed after the merge.
- Next: the fourth artwork kind (background/fanart, `TODO.md`); its
  arrival is when the preview sizes get revisited. Then the other game
  sources (Epic, GOG) with a per-source batch import, and the 1.0
  packaging check (AppImage and recipes must ship `icoextract`/`pefile`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
