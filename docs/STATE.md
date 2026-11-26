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
- Landed: seventy-seven batches. The latest settles the sidebar: a
  category name is elided to the width left by its count (count outside
  the elide, full label in the tooltip), the sidebar opens 12 grid units
  wide and Kirigami's edge handle resizes it (10–25 units, persisted as
  `[ui] drawer_width`), and the elide follows the drawer's real width.
  The drag-persistence debounce and the Preferences slider were reverted
  at the maintainer's request; the edge drag itself stores the width.
  Before it, the Lutris/Faugus import mapping landed (version split,
  defaults as the base, Gamescope, MangoHud env vars) and batch Download
  Metadata (selection list, title search, fill-empty Apply). The sidebar
  categories stay manual.
- Verified: `scripts/check.sh --qml` (858 passed, 3 skipped, including
  the QML driver) on the approved diff, and the venv refreshed after the
  commit.
- Next: the name-suffix batch sits uncommitted in `stash@{0}`
  (`name-suffixes WIP: version+tag suffixes`): `split_name_suffixes`
  reads `(State Tag)` and a mid-name `[vN]` back beside the version,
  used by import and the dialog save. Restore it, review, commit and
  land. Then the 1.0 gate waits on the maintainer's release call (visual
  pass, shim removal, translations, release pass). Playnite is parked for
  3.0, only if another operating system is supported. Epic/GOG is 2.0,
  and so is the IGDB per-user credential review.
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
