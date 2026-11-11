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
- Landed: thirty-nine batches. The latest orders the roadmap: metadata
  provider, library import, the 1.0 gate, then Epic/GOG in 2.0;
  `TODO.md` splits into Before 1.0 and 2.0 with the why of each phase.
- Verified: the docs batch by `pytest tests/test_docs.py` (6 passed).
- Next: the metadata provider client — decision record, IGDB credential,
  client, cache, rate limit — then its consumers (local metadata,
  provider artwork, online categories), then the library import and its
  enrichment; 1.0 ships both themes. Epic/GOG is 2.0. The 1.0 visual
  pass, the packaging check, the compatibility-shim removal and the
  release pass wait for the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: four block the first theme —
  `docs/plans/metadata-provider.md` (service, credential, overwrite
  policy, cache shape). `docs/plans/epic-gog-sources.md` is parked for
  2.0 with its own four decisions (scope, discovery, launch, import UI).
- Nothing blocking.
