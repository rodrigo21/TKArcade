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
- Landed: eighty-six batches. The latest: Download Metadata's preview
  became a per-field comparison. The Current and New columns carry a
  checkbox per value (an exclusive pair for scalars), the headers act on
  a whole column while starting unchecked, the New column names its
  provider, and Apply writes exactly the checked selection. Lists render
  inline under the window's single scroll; the window opens half the work
  area wide and at its whole height; a value the game already carries
  (list name or scalar text) is struck through, dimmer and unchecked;
  the description compares in two six-line scrolling boxes; Reset
  discards the fetched answer. Developer, publisher and genre split on
  `;`. Before it: the Wayland app id fix.
- Verified: `scripts/check.sh --qml` (890 passed, 3 skipped) on the
  landed diff; the maintainer tested the first preview pass on the real
  display and the scalar/description fixes were confirmed offscreen. The
  backdrop render confirmed the sharp fit, but the software scenegraph
  draws no `MultiEffect` pixels, so the blur needs a real-display check.
  The venv was refreshed after the merge.
- Next: the 1.0 gate waits on the maintainer's release call (visual
  pass, shim removal, translations, release pass). On the real display,
  check the backdrop blur, the **Release Cover** row for a VNDB game with
  a release pick, and the long combos in the large windows (Wine, Proton,
  DXVK, vkd3d, language, release), which share the window height and were
  not opened one by one. Playnite is parked for 3.0, only if another
  operating system is supported. Epic/GOG is 2.0, and so is the IGDB
  per-user credential review.
- Deferred: the audit's #15 (launch parse) and #19 (role constants) in
  `TODO.md`.
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
