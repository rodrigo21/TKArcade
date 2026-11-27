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
- Landed: eighty-two batches. The latest two: the chooser keeps a kind
  (a second click deselects it, so the confirm neither downloads nor
  chain-fills that kind), offers the source's banner candidates as a
  Background section with **Use the Banner** copying the chosen banner
  instead of downloading it twice, and grew the cover and wide
  previews; the library backdrop now shows the whole background
  picture, a sharp aspect-fit copy over a blurred cropped copy that
  fills the page. Resolved identities are stored on confirm, and
  previews stay in Qt memory rather than the artwork cache.
- Verified: `scripts/check.sh --qml` (883 passed, 3 skipped) on the
  landed diff. The offscreen chooser screenshot showed no clipping; the
  backdrop render confirmed the sharp fit, but the software scenegraph
  draws no `MultiEffect` pixels, so the blur needs a real-display check.
  The venv was refreshed after both merges.
- Next: the 1.0 gate waits on the maintainer's release call (visual
  pass, shim removal, translations, release pass); check the backdrop
  blur on a real display first. Playnite is parked for 3.0, only if
  another operating system is supported. Epic/GOG is 2.0, and so is the
  IGDB per-user credential review.
- Deferred: the audit's #15 (launch parse), #19 (role constants) and the
  VNDB release-cover variants in `TODO.md`.
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
