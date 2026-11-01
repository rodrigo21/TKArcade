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
- Landed: the graphics decision record (`docs/decisions/graphics-layers.md`):
  `[graphics]` stays a plain-Wine feature because Proton prepends its
  dist to `WINEDLLPATH` and appends its overrides, so only replacing
  the runtime install could override per game — shared state reset by
  updates. README and TODO updated; docs-only, no code.
- Verified: `tests/test_docs.py` 6 passed and `scripts/check.sh
  --changed` 10 passed (docs-only batch). venv unchanged
  (`0.0.0.post613.dev0+57e4a35`). No real-display or real Steam library
  test.
- Next: filter the Steam Compat Tool list (`proton.list_compat_tools()`
  plus the system-wine row appended in `GuiModel.wineTools()`). It
  currently offers `Proton EasyAntiCheat Runtime`, `Proton BattlEye
  Runtime` and `System wine (...)`, none usable as a compat tool: the
  anti-cheat runtimes are Steam-internal tools without a Proton/DXVK
  tree, and system wine is not an installed Steam tool at all, so
  `applyWineVersion` writes a name Steam ignores. Keep only real Proton
  builds (a `proton` launcher inside) and drop the appended wine row;
  the umu Proton picker is a separate model.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
