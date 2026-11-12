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
- Landed: forty-five batches. The latest is C7: IGDB as the third
  artwork provider (cover and banner from `[metadata] igdb_id`, no
  name search, no icon) and the fallback order fixed for three sources.
  Before it, C6: the IGDB metadata adapter, the Twitch credentials
  (`[ui] igdb_client_id`/`igdb_client_secret`), the Metadata Source menu
  on Details and `[metadata] igdb_id`. C5 (PCGamingWiki) is dropped:
  Cloudflare answers a plain HTTP client, and IGDB carries its fields.
- Verified: `scripts/check.sh --changed` with the QML driver (747
  passed, 3 skipped) and offscreen screenshots of the Metadata rows,
  the Preferences Metadata section and the art provider popup.
- Next: C8, online categories/tags in bulk, then the library import. A
  real-key IGDB smoke test waits on the maintainer's Twitch
  application; the adapters and their fixtures do not. Epic/GOG is 2.0.
  The 1.0 visual pass, the packaging check, the shim removal and the
  release pass wait for the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none block C8. `docs/plans/epic-gog-sources.md` is
  parked for 2.0 with its own four decisions (scope, discovery, launch,
  import UI).
- Nothing blocking.
