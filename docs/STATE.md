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
- Landed: `AGENTS.md` now requires the maintainer's explicit approval
  before any file change, stage, commit or push (investigate read-only,
  present a plan, wait). Git rules live in `docs/GIT.md` (ambient), with
  `AGENTS.md`, `DEVELOPMENT.md`, `POLICIES.md`, the document map and
  the handoff command pointing there; `STATE.md` no longer records
  commit hashes. The Artwork Status row says "Artwork Cleared" while
  the source AppID keeps its cleared mark, instead of showing art that
  never arrived. The cards banner consumes the per-game cover (icon
  fallback) and fits the art to its own aspect instead of cropping a
  portrait cover; `docs/QML-NOTES.md` keeps the rule. The Status
  messages lost the repeated "Use Fetch Artwork" wording that wrapped
  at the 612 px settings minimum.
- Before it: every dialog in the shell is a separate modal `Window`
  (`ConfirmDialog.qml` for confirmations, `DialogWindow.qml` for inputs
  and reports; no `Kirigami.Dialog` left), the per-game `[metadata]`
  fields, and every view's keyboard navigation.
- Verified: 482 tests with the QML driver before landing (known
  unrelated batch-abort retries), 481 fast tests on `main` after, docs
  contract 6 passed after the git-rules reorg (`scripts/check.sh
  --changed` 10 passed), and offscreen cards with portrait
  cover/icon/no art plus the Artwork Status at the 612 px minimum. Venv
  refreshed after the merge.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
