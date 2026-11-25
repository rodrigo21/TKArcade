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
- Landed: seventy-two batches. The latest adds the VNDB release
  picker: Search Data lists the releases linked to a VNDB identity, a
  client-side language filter narrows them, the pick drives Release Date
  and Publisher, and `[metadata] vndb_release` re-keys the cache for the
  next download. Before it, Download Metadata merged the list fields
  (tags append, an age rating replaces its own board) and the venv
  refresh rule moved into `docs/DEVELOPMENT.md` and `docs/GIT.md`.
- Verified: `scripts/check.sh --qml` (832 passed, 3 skipped) on the
  approved diff, the offscreen Search Data screenshot
  (`/tmp/opencode/vndb-release.png`) and `tests/test_docs.py` re-run
  green after the decision record. The venv was refreshed after the
  merge.
- Next: the library format import needs a plan before its first reader
  (per-format readers for Lutris and Faugus, the ID/name mapping and an
  ImportDialog page). The tag follow-ups wait for it (library import tag
  mapping, display polish). After the import, decide whether sidebar
  categories derive from tags and whether a bulk download is worth it.
  Playnite is parked for 3.0, only if another operating system is
  supported. Epic/GOG is 2.0, and so is the IGDB per-user credential
  review.
- Deferred: the audit's #15 (launch parse) and #19 (role constants).
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  The venv is the only build under test: refresh it before a test round
  and after every commit and merge (`docs/GIT.md`); the agent never
  installs the app on the system (no `makepkg -i`, `pacman -U`, writes
  under `/usr`). Package builds belong to the maintainer. Translations
  stay suspended (English-only new strings) until the 1.0 pass restores
  the catalog.
- Local: an earlier `makepkg -f` left a package at r810 in
  `~/Curioso/Packages/makepkg/Packages/`; nothing is installed, and the
  installed app stays at r799.
- Open decisions: none block the next theme.
  `docs/plans/epic-gog-sources.md` is parked for 2.0 with its own four
  decisions (scope, discovery, launch, import UI).
- Nothing blocking.
