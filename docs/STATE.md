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
- Landed: forty-seven batches. The latest is the Search Data window: one
  modal per game (opened from the Information title) with a Metadata tab
  (source Steam/VNDB/IGDB/ProtonDB, name-or-id search, candidate
  buttons, identity fields, preview rows, Replace) and an Artwork tab
  (the four slots, Source AppID, Download From, Fetch/Clear). The
  Details tab lost the source menu, the Download Metadata action and the
  Steam/VNDB/IGDB fields, gained a `Matches:` line and a four-tile art
  strip, kept the ProtonDB badge and the Tags row with its Clear, and
  Notes moved to its end: six tabs. A new Steam game also fills its
  store metadata on save (fill-empty, locks respected, tags and date
  included). Record: `docs/decisions/metadata-window.md`.
- Verified: `scripts/check.sh --qml` (753 passed, 3 skipped), `qmllint`,
  `tests/test_docs.py`, offscreen screenshots of Details, the Add dialog
  and both window tabs at normal, minimum and intermediate widths.
- Next: the maintainer's new changes (not scoped yet), then the library
  import. Open follow-up: after the import, decide whether categories
  derive from tags, whether the tags get a filter/editor and whether a
  bulk download is worth it. Epic/GOG is 2.0, and so is the IGDB
  per-user credential review (`TODO.md`). The 1.0 visual pass, the
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
