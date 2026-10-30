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
- Landed: the Profile selector shows the profile names again — its
  combo declared a `display` text role over a plain string list, which
  blanked the field and the popup rows; the model now carries
  `{text, data}` rows with `textRole: "text"`. The tooltip sweep found
  no other empty bubble in the shell.
- Before it: the landing gate (`AGENTS.md` + `docs/GIT.md`), then the
  profile controls moved above the settings tabs.
- Verified: `scripts/check.sh --changed` 482 passed (full QML driver)
  plus the three profile cases in isolation; offscreen screenshots show
  the active name on General and Runtime. Venv refreshed after the
  merge.
- Next: the categories redesign (the per-game artwork provider override
  was rejected, see `docs/decisions/artwork-provider.md`); later the
  deferred DXVK, external-runtime and preferences/Global Defaults design
  reviews, and the release pass.
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post533.
- Nothing blocking.
