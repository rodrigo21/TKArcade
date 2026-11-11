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
- Landed: forty batches. The latest turns the provider plan into a
  registry (Steam, VNDB, PCGamingWiki, IGDB) with a preview before
  writing, per-field locks and the date as a fillable field; IGDB waits
  on a Twitch app key.
- Verified: the docs batch by `pytest tests/test_docs.py` (6 passed).
- Next: C1, the registry plus the Steam adapter (no key, no UI change),
  then the action UI, the field locks, VNDB, PCGamingWiki, IGDB, IGDB
  artwork and online categories; the library import follows. Epic/GOG
  is 2.0. The 1.0 visual pass, the packaging check, the shim removal and
  the release pass wait for the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none block C1; C6 waits on the maintainer's Twitch
  application (client id/secret). `docs/plans/epic-gog-sources.md` is
  parked for 2.0 with its own four decisions (scope, discovery, launch,
  import UI).
- Nothing blocking.
