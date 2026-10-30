# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  packaging churn in `packaging/arch/tkarcade-git/` (`PKGBUILD`
  `pkgver` and an untracked `.SRCINFO`, never committed); `.qoder/` is
  git-ignored.
- Landed: the profile controls (active selector plus Save As/Clone/
  Delete behind an overflow menu) moved from the General tab to a bar
  above the settings tabs, visible on every page.
- Before it: `AGENTS.md` corrects how plan mode is entered — the
  maintainer toggles it with `/plan` (no confirmation either way), the
  agent asks for `/plan` instead of calling `EnterPlanMode`, and
  `ExitPlanMode` remains the approval gate before execution.
- Verified: `scripts/check.sh --changed` 482 passed (full QML driver)
  after the header-bar change, plus offscreen screenshots on General
  and Runtime at default and minimum width and the menu entries; the
  plan-mode rule edit before it ran 10. Venv refreshed after the merge.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
