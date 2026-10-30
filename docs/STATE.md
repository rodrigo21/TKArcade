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
- Landed: the General tab's read-only identifier reads `App ID` instead
  of `Steam App ID`, since local games carry one too. The title action
  tooltips only open in compact icon-only mode and a Played cell with
  no sessions shows none; `docs/QML-NOTES.md` keeps the rule.
  Translations refreshed; the approved plan formalized the two fixes.
- Before it: `AGENTS.md` requires explicit approval before any change,
  the git rules live in `docs/GIT.md` (ambient), and the artwork
  leftovers (cleared status, card covers, banner aspect) landed.
- Verified: 482 tests with the QML driver before landing (known
  unrelated batch-abort retries), the `App ID:` label rendered offscreen
  at the General tab, and the translation refresh reported 0
  untranslated/unfinished. Hover itself is not delivered by the
  offscreen driver, so the tooltip guard was checked by binding. Venv
  refreshed after the merge.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
