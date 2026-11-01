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
- Landed: two batches. The graphics decision record
  (`docs/decisions/graphics-layers.md`): `[graphics]` stays a
  plain-Wine feature because Proton prepends its dist to `WINEDLLPATH`
  and appends its overrides, so only replacing the runtime install could
  override per game — shared state reset by updates. Then the Compat
  Tool filter: the Steam game's combo lists only directories holding the
  `proton` launcher, so the anti-cheat runtime tools and the appended
  System wine row are gone (`system_wine()` deleted).
- Verified: `scripts/check.sh --changed` 512 passed on the filter
  branch plus its one new backend test; docs batch covered by
  `test_docs`/`test_packaging`. venv refreshed after the merge
  (`0.0.0.post618.dev0+6ea48bc`). No real-display or real Steam library
  test.
- Next: pick from the `TODO.md` "Deferred design review" items —
  external runtime versions (Lutris-like) or the Preferences/Global
  Defaults content audits.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
