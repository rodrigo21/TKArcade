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
- Landed: `AGENTS.md` corrects how plan mode is entered — the
  maintainer toggles it with `/plan` (no confirmation either way), the
  agent asks for `/plan` instead of calling `EnterPlanMode`, and
  `ExitPlanMode` remains the approval gate before execution.
- Before it: `AGENTS.md` makes the implicit rules explicit — plan mode
  starts every session, one theme per batch with `/handoff` then plan
  mode, tests in temporary XDG/HOME, declare checks not run, translation
  and POLICIES routing, README/man updates for CLI changes, diff review
  and no discarded work or committed secrets; `docs/GIT.md` carries the
  detail.
- Verified: `scripts/check.sh --changed` 10 passed (docs contract plus
  packaging) after the plan-mode rule edit; before it, the rules edit
  ran the same 10 and the GUI landing 482 QML tests plus the offscreen
  `App ID:` label. Venv refreshed after the change.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
