# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  `pkgver` churn in `packaging/arch/tkarcade-git/PKGBUILD` (never
  committed); `.qoder/` is git-ignored.
- Landed: `AGENTS.md` makes plan mode the default and states entering
  it needs no approval while leaving to execute does: stay there until
  the plan is approved, execute only that scope, and re-enter after
  commit, push and handoff. `docs/GIT.md` points there and treats the
  handoff commit as the close of the landing batch; `STATE.md` stays a
  state file, not policy.
- Before it: the `App ID` label and empty-tooltip fixes, the approval
  rule, the git-rules reorg into `docs/GIT.md`, and the artwork
  leftovers (cleared status, card covers, banner aspect).
- Verified: docs contract 6 passed and `scripts/check.sh --changed`
  10 passed after the workflow docs edit; the previous GUI landing had
  482 QML tests, the offscreen `App ID:` label and a clean translation
  refresh. Venv refreshed after the merge.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
