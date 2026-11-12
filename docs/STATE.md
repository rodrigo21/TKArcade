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
- Landed: forty-six batches. The latest is C8: online tags. The three
  providers return a `tags` list (Steam genres, store features and
  franchise; IGDB genres, franchise, themes and keywords; VNDB
  non-spoiler tags rated 2.0+, top 20), Download Metadata previews a
  Tags row and writes `[metadata] tags`, and Details shows the list
  read-only next to Series. Categories stay manual. There is no bulk
  tag action: it was built and removed at the maintainer's call. The
  metadata cache payload carries `CACHE_VERSION = 2`.
- Verified: `scripts/check.sh --qml` (750 passed, 3 skipped) and
  offscreen screenshots of the Details Tags row and the metadata
  preview.
- Next: the maintainer's new changes (not scoped yet), then the library
  import. Open follow-up: after the import, decide whether categories
  derive from the tags, whether the tags get a filter/editor and whether
  a bulk download is worth it. Epic/GOG is 2.0. The 1.0 visual pass, the
  packaging check, the shim removal and the release pass wait for the
  maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none block the next theme.
  `docs/plans/epic-gog-sources.md` is parked for 2.0 with its own four
  decisions (scope, discovery, launch, import UI).
- Nothing blocking.
