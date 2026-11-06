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
- Landed: sixteen batches. The latest one: a Steam game's Runtime is
  preselected from Steam's compat mapping (the game's own entry, else
  the default tool) and Detected Runtime names that tool with its
  version instead of a bare "Proton"; the Scan dialog is gone, Add Game
  is the only way to add a Steam game. Before it: the ProtonDB tier,
  release date and artwork fetch for a newly added game, and the
  `commit-msg` hook naming the model in both trailers. Earlier: the
  executable icon for local games (`icoextract`), the Artwork tab
  previews, the dialog opening at half the screen width and full usable
  height, and the test policy (full suite once per approval round).
- Verified: `scripts/check.sh` 652 passed and `scripts/check.sh --qml`
  653 passed on that diff; venv refreshed after the merge.
- Next: the fourth artwork kind (background/fanart, `TODO.md`); its
  arrival is when the preview sizes get revisited. Then the other game
  sources (Epic, GOG) with a per-source batch import, and the 1.0
  packaging check (AppImage and recipes must ship `icoextract`/`pefile`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
