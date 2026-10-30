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
- Landed: `AGENTS.md` makes the implicit rules explicit — plan mode
  starts every session, one theme per batch with `/handoff` then plan
  mode, tests in temporary XDG/HOME, declare checks not run, translation
  and POLICIES routing, README/man updates for CLI changes, diff review
  and no discarded work or committed secrets. `docs/GIT.md` carries the
  detail.
- Before it: plan mode as the default workflow and the `App ID` label
  and empty-tooltip fixes.
- Verified: docs contract 6 passed and `scripts/check.sh --changed`
  10 passed after the rules edit; the GUI landing before it had 482 QML
  tests, the offscreen `App ID:` label and a clean translation refresh.
  Venv refreshed after the merge.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
