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
- Landed: fifteen batches. The latest ones: a game added from Scan or
  the game dialog now fetches its ProtonDB tier, release date and
  artwork at once instead of on the next start; the `commit-msg` hook
  names the model in both trailers (`.opencode-model` holds the display
  name, the tool name stays as the empty-file fallback). Before them:
  the executable icon for local games (`icoextract`, last icon
  fallback), the Artwork tab previews (framed icon/banner/cover tiles at
  the image's own size, click to pick, URL download to a manual slot,
  per-kind Clear, origin and zoom in the tooltip), the dialog opening at
  half the screen width and full usable height, and the test policy
  (full suite once per approval round, targeted runs while iterating).
- Verified: `scripts/check.sh` 650 passed and `scripts/check.sh --qml`
  651 passed on the fetch change; the hook change adds no test (nothing
  covers the hook, and one would need `git init` inside a test); venv
  refreshed after both commits.
- Next: the agreed-but-unimplemented runtime detection for Steam games
  (preselect Proton/Native from Steam's `CompatToolMapping`, the game's
  own entry or the `"0"` default; show that default compat tool in
  Detected Runtime instead of a bare "Proton"). After that, the fourth
  artwork kind (background/fanart, `TODO.md`); its arrival is when the
  preview sizes get revisited. Then the 1.0 packaging check (AppImage
  and recipes must ship `icoextract`/`pefile`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  and `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
