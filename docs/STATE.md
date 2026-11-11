# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's `pkgver` churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: thirty-eight batches. The latest: the library's ProtonDB
  badge shows a pending game as grey text on grey (`#757575`) instead
  of an unreadable black bar, in the list, card and game dialog;
  `TIER_STYLE` gained a `pending` entry and a model test pins the row
  values. Before it: Download Metadata closes the
  Details Game section, beside the Steam AppID and ProtonDB rows it
  depends on, and fills empty description/developer/publisher/genre/
  series/age ratings from the Steam store for a Steam ID or a local
  game's `[metadata] steam_appid`. It keeps typed values, caches per
  game in `steam-meta` with the target recorded, and maps ESRB/PEGI/USK
  only; the manual date stays manual. The store rows moved out of
  Information, so Information holds the manual fields plus the
  elastic five-line Description. Before it: the description box fill
  and scroll, the local game's ProtonDB store link, the fourth artwork
  kind `background`, and the game dialog rework (Details/Execution tabs,
  manual `[metadata]` fields, status badges, ProtonDB row). Translations
  were suspended until 1.0 (`tests/test_i18n.py` catalog tests are
  skipped).
- Verified: the approved diff. 702 passed, 3 skipped with the QML
  driver (`scripts/check.sh --qml`); the badge change touches no QML,
  and the earlier layout comparison (`/tmp/opencode/compare-linked.png`)
  and metadata screenshots still stand.
- Next: the other game sources (Epic, GOG). The metadata-provider
  consolidation (other artwork sources, a provider for local games
  without a Steam link, Playnite enrichment, online categories) is
  proposed in the TODO items, not decided. The 1.0 visual pass, the
  packaging check, the compatibility-shim removal and the release pass
  wait for the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none blocking. Two proposals wait on you:
  `docs/plans/epic-gog-sources.md` (scope, discovery, launch, import UI)
  and `docs/plans/metadata-provider.md` (provider, credential, overwrite
  policy, cache shape).
- Nothing blocking.
