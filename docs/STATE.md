# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: thirty-six batches. The latest: the Details description box
  fills the space the other sections leave, stretches with the window,
  shrinks to five lines and scrolls long text inside its own frame (it
  stays in the Information section). Before it: a local game's
  `[metadata] steam_appid` links its Steam store page, so the ProtonDB
  table column, Details rating and context menu work for it; the cache
  stays keyed by the game ID and records the AppID it was fetched for.
  Earlier: the fourth artwork kind `background` (`[artwork] background`,
  its own manual slot, config key and cache name, falling back to the
  banner), the game dialog rework (Details/Execution tabs, manual
  `[metadata]` fields, status badges, ProtonDB row), the Wine
  column/Compat Tool work, and translations were suspended until 1.0
  (`tests/test_i18n.py` catalog tests are skipped).
- Verified: the approved diffs. 693 passed, 3 skipped with the QML driver
  (`scripts/check.sh --qml`); the description screenshots are
  `/tmp/opencode/description-empty.png` and
  `/tmp/opencode/description-long.png`.
- Next: the other game sources (Epic, GOG). The metadata-provider
  consolidation (other artwork sources, metadata download, Playnite
  enrichment, online categories) is proposed in the TODO items, not
  decided. The 1.0 visual pass, the packaging check, the
  compatibility-shim removal and the release pass wait for the
  maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`,
  `docs/decisions/artwork-background.md` and
  `docs/decisions/exe-icon.md` cover the artwork work.
- Nothing blocking.
