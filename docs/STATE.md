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
- Landed: seventy-five batches. The latest adds batch Download
  Metadata: `Download Metadata…` in the selection menu lists every
  chosen game, resolves each row off the GUI thread (stored identity
  first, else a title search in the chosen source) and shows the match
  plus the fields it would fill. The worker never writes; Apply fills
  empty fields, respects locks, writes the lists only when empty and
  stores a searched identity. No artwork or ProtonDB in a batch. It
  closes the online-tags follow-up: the sidebar categories stay manual.
  Before it, the VNDB release picker landed (`[metadata] vndb_release`
  drives Date and Publisher).
- Verified: `scripts/check.sh --changed` (853 passed, 3 skipped,
  including the QML driver) on the approved diff, the dialog screenshot
  (`/tmp/opencode/bulk-metadata-dialog.png` and `-checked.png`), and the
  venv refreshed after the merge.
- Next: the import mapping fixes the maintainer reported — the name's
  trailing `[version]` must split at read time, imported configs must
  start from Global Defaults (profiles from the live config), Lutris
  MangoHud/Gamescope must map onto `[mangohud]`/`[gamescope]`
  (`gamescope_flags`, window mode, resolutions, fps limiter), and
  `MANGOHUD`/`MANGOHUD_DLSYM`/`MANGOHUD_CONFIGFILE` must become native
  options instead of env vars. Also open: the sidebar category labels
  overrun the drawer width (decide elide/tooltip, wrap or a manual
  width). Then the 1.0 gate waits on the maintainer's release call
  (visual pass, shim removal, translations, release pass). Playnite is
  parked for 3.0, only if another operating system is supported.
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
