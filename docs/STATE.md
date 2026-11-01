# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  packaging churn in `packaging/arch/tkarcade-git/` (`PKGBUILD`
  `pkgver`, `optdepends` indentation and a lenient `check()`, plus an
  untracked `.SRCINFO`, never committed); `.qoder/` is git-ignored.
- Landed: three batches. The graphics decision record
  (`docs/decisions/graphics-layers.md`): `[graphics]` stays a
  plain-Wine feature because Proton prepends its dist to `WINEDLLPATH`
  and appends its overrides, so only replacing the runtime install could
  override per game — shared state reset by updates. Then the Compat
  Tool filter: the Steam game's combo lists only directories holding the
  `proton` launcher, so the anti-cheat runtime tools and the appended
  System wine row are gone (`system_wine()` deleted). Last, the settings
  placement audit (`docs/decisions/settings-placement.md`): Preferences
  is four sections (Interface, Tray, Artwork, Runtime) with one label
  column, and the Global Defaults template carries launch behaviour only
  — `save_defaults()` drops `[metadata]`, `[runtime]`, `[graphics]`,
  `[audio]`, `[debug]`, `[artwork]`, `[notes]` and the per-game General
  keys; the Runtime tab is disabled with a note and the Game/Audio
  sections hide in defaults mode. New games start with no runtime until
  one is chosen (the launcher exits 18).
- Verified: `scripts/check.sh --qml` 514 passed on the settings branch;
  offscreen screenshots covered the four Preferences sections and the
  defaults trims; translations 0 unfinished. venv refreshed after the
  merge. No real-display or real Steam library test.
- Next: the last `TODO.md` "Deferred design review" item — external
  runtime versions (Lutris-like).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
