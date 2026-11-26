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
- Landed: seventy-four batches. The latest adds the Lutris and Faugus
  library import: read-only readers (`pga.db` + YAML, `games.json`),
  live configs for new games and `lutris`/`faugus` profiles for
  existing ones, `[store] kind`/`id`, exact external prefixes
  (`[runtime] prefix_exact`) and a checkable ImportDialog page with
  `In Library`/`Unavailable` rows. Paths are never stat'ed; a
  disconnected autofs drive disables its rows, and the readers run off
  the GUI thread. Before it, the VNDB release picker landed
  (`[metadata] vndb_release` drives Date and Publisher).
- Verified: `scripts/check.sh --changed` (849 passed, 3 skipped,
  including the QML driver) on the approved diff, the import
  screenshots (`/tmp/opencode/import-library-state.png`), a read-only
  Lutris scan (473 games in 0.25s, 15 offline rows), Faugus fixtures
  (the local library is empty), and the venv refreshed after the merge.
- Next: the online-tags follow-up — decide whether sidebar categories
  derive from tags and whether a bulk download is worth it. The import
  mapped foreign categories to `[general] categories`, so the old tag
  mapping item is closed. The 1.0 gate waits on the maintainer's
  release call (visual pass, shim removal, translations, release pass).
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
