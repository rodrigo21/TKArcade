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
- Landed: seventy-one batches. The latest makes Download Metadata merge
  the list fields: the accepted provider tags append to the game's own
  list and an age rating replaces only its own board, the Replace
  switch still swaps whole lists, and the preview's New column shows
  the merged result. Before it, the venv refresh rule moved into
  `docs/DEVELOPMENT.md` and `docs/GIT.md` (refresh before a test round
  and again after every commit and merge), and the tag filter counts
  followed the active filters.
- Verified: `scripts/check.sh --qml` (820 passed, 3 skipped; its one
  docs failure was fixed and `tests/test_docs.py` re-ran green) plus the
  offscreen Search Data screenshot (`/tmp/opencode/metadata-merge.png`).
  The venv was refreshed after the merge.
- Next: the VNDB release picker plan is
  `docs/plans/vndb-release-picker.md`; implement its batch 2 (adapter,
  `[metadata] vndb_release`, registry `release` channel) after approval.
  Then the remaining tag follow-ups in `TODO.md` (library import tag
  mapping, display polish). After the library import, decide whether
  sidebar categories derive from tags and whether a bulk download is
  worth it.
  Epic/GOG is 2.0, and so is the IGDB per-user credential review.
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
