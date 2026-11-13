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
- Landed: forty-eight batches. The latest fixed the Search Data and
  artwork behaviour the maintainer reported: **Clear** now empties the
  tile for real — the ✕ deletes that kind's downloaded copy, and both
  Clear buttons write marks (`cleared` / `cleared_kinds` in the artwork
  sidecar) that hide Steam's own art, the exe icon and the
  cover/banner siblings until **Fetch Artwork**; a manual pick or a
  forced fetch drops the marks. The Steam metadata source gained the
  store title search (`storemeta.search`), looks a known AppID up as the
  window opens with no Find row (a local game's store link refetches when
  edited), and the month-first release date ("Jun 11, 2021") parses,
  bumping the metadata cache to version 3. The Search Data window is
  30 grid units and both tabs scroll, so fields start at the top. Record:
  the CHANGELOG entry; VNDB releases are parked in `TODO.md`.
- Verified: `scripts/check.sh --qml` (758 passed, 3 skipped), `qmllint`
  on `GameSettings.qml`, and six offscreen screenshots (Metadata with and
  without rows, a local game at default and minimum width, Artwork at both
  widths): no clipped control, no blank band above the first row.
- Next: the maintainer's new changes (not scoped yet), then the library
  import. The VNDB release picker sits in `TODO.md` before 1.0. Open
  follow-up: after the import, decide whether categories derive from
  tags, whether the tags get a filter/editor and whether a bulk download
  is worth it. Epic/GOG is 2.0, and so is the IGDB per-user credential
  review (`TODO.md`). The 1.0 visual pass, the packaging check, the shim
  removal and the release pass wait for the maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none block the next theme.
  `docs/plans/epic-gog-sources.md` is parked for 2.0 with its own four
  decisions (scope, discovery, launch, import UI).
- Nothing blocking.
