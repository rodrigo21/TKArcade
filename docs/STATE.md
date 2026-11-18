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
- Landed: sixty-eight batches. The latest lets the Search Data preview
  pick the tags to apply: the Tags row is a button (first tag plus how
  many follow, full list in the tooltip) that opens the picker with
  every provider name checked, and declining them all writes no tags.
  It also fixed two rendering bugs: the hidden button no longer widens
  the preview row, and the button sets no `contentItem`, because the
  Plasma style paints its own text. Before it, the optional **Tags**
  column and **Set Tags…** with the persistent filter.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh --changed` and `scripts/check.sh --qml`
  (820 passed, 3 skipped) on the approved diff, plus offscreen
  screenshots with `QT_QUICK_CONTROLS_STYLE=org.kde.desktop` (the
  Fusion default hid the doubled button text). The venv was refreshed
  after the merge and `makepkg -f` built the `-git` package at
  r810.g23c8835; installing it needs the maintainer's sudo.
- Next: **tag filter counts** reflect the AND selection instead of
  every game carrying the tag; then the metadata merge policy decision,
  the VNDB release picker and the remaining tag follow-ups in `TODO.md`
  (import mapping, display polish). After the library import, decide
  whether categories derive from tags and whether a bulk download is
  worth it. Epic/GOG is 2.0, and so is the IGDB per-user credential
  review (`TODO.md`). The 1.0 visual pass, the packaging check, the
  shim removal and the release pass wait for the maintainer's release
  call.
- Deferred: the audit's #15 (launch parse) and #19 (role constants).
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  The venv is the only build under test; the agent never installs the
  app on the system (no `makepkg -i`, `pacman -U`, writes under
  `/usr`). Package builds belong to the maintainer, on the packaging or
  release subject. Translations stay suspended (English-only new
  strings) until the 1.0 pass restores the catalog.
- Open decisions: none block the next theme.
  `docs/plans/epic-gog-sources.md` is parked for 2.0 with its own four
  decisions (scope, discovery, launch, import UI).
- Nothing blocking.
