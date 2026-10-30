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
- Landed: `AGENTS.md` and `docs/GIT.md` gate the landing on a second
  approval — an approved plan covers the branch work and its commit;
  with the venv refreshed, the maintainer approves the changes before
  squash-merge, push or `/handoff`.
- Before it: the profile controls (active selector plus Save As/Clone/
  Delete behind an overflow menu) moved from the General tab to a bar
  above the settings tabs, visible on every page.
- Verified: docs contract 6 passed after the approval-gate edit; the
  header-bar landing before it ran `scripts/check.sh --changed` 482
  passed (full QML driver) plus offscreen screenshots on General and
  Runtime at default and minimum width. Venv refreshed after each
  landing.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
