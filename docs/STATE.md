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
- Landed: sixty-nine batches. The latest makes the tag filter counts
  follow the active filters: source, text, issues, category and the tag
  selection (AND) narrow every number, while Match Any keeps the plain
  per-tag count because checking a name can only widen. The popup binds
  one live map, so no rows are rebuilt. The title-row width test lost
  its brittle 200 px floor. Before it, the Search Data preview tag
  picker and the optional **Tags** column.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh --qml` (821 passed, 3 skipped) on the
  approved diff, plus the offscreen popup screenshot with the counts
  (`/tmp/opencode/tag-counts.png`). The venv was refreshed after the
  merge. An earlier `makepkg -f` left a package at r810.g23c8835 in
  `~/Curioso/Packages/makepkg/Packages/`; nothing is installed, and the
  installed app stays at r799.
- Next: the metadata merge policy decision (does a download add to an
  existing tag/age-rating list), then the VNDB release picker and the
  remaining tag follow-ups in `TODO.md` (import mapping, display
  polish). After the library import, decide
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
