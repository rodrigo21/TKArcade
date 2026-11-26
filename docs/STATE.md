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
- Landed: seventy-eight batches. The latest reads the name's display
  suffixes back: `split_name_suffixes` lifts a trailing `(State Tag)`
  into `[metadata] tag` and a `[vN]` token (even mid-name) into
  `[metadata] version`, used by the import and the dialog save; a
  trailing bracket must look like a version, so `[ENG]`/`[Repack]` stay.
  Before it, the sidebar settles at 12 units (10–25 by dragging) with
  the category elide, the import mapping landed (defaults as the base,
  Gamescope, MangoHud env vars) and batch Download Metadata (selection
  list, title search, fill-empty Apply). The sidebar categories stay
  manual.
- Verified: `scripts/check.sh` (858 passed, 3 skipped) before the merge,
  and the venv refreshed after the commit.
- Next: the 1.0 gate waits on the maintainer's release call (visual
  pass, shim removal, translations, release pass). Playnite is parked
  for 3.0, only if another operating system is supported. Epic/GOG is
  2.0, and so is the IGDB per-user credential review.
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
