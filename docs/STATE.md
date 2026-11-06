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
- Landed: thirteen batches. The latest ones: the executable icon for
  local games (`icoextract`, last icon fallback), the Artwork tab
  previews (framed icon/banner/cover tiles at the image's own size,
  click to pick, URL download to a manual slot, per-kind Clear, origin
  and zoom in the tooltip), the dialog opening at half the screen width
  and full usable height, and the test policy (full suite once per
  approval round, targeted runs while iterating).
- Verified: `scripts/check.sh` 649 passed and `scripts/check.sh --qml`
  650 passed; offscreen screenshots of the Artwork tab at 100% and
  150% (tooltips of cover and banner included); venv refreshed after
  the merge.
- Next: the fourth artwork kind (background/fanart, `TODO.md`); its
  arrival is when the preview sizes get revisited. After that, the
  remaining deferred research and the 1.0 packaging check (AppImage and
  recipes must ship `icoextract`/`pefile`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
