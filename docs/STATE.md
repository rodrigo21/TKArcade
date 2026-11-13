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
- Landed: fifty batches. The latest two polished the game dialog and
  added the metadata locks. Details shows one banner preview at the
  Artwork tab's shape (tooltip opens the tab); Search Data is a framed
  icon beside the Information title and its Search moved to the dialog
  footer (`DialogWindow.leadingActions`); ProtonDB left the Metadata
  sources (it only re-read its cache), the local game's badge gained a
  find button that opens the Steam title search with or without a link,
  and the badge opens the page on a double-click. Fetch Artwork now
  drops every cleared mark, including the background, which has no
  download of its own. The online Tags list joined the lockable fields,
  and a lock button beside the Game title sets or clears every field
  lock at once while each row keeps toggling on its own; the icon-only
  buttons became framed 32 px squares because the theme's ToolButton
  draws no frame. Record: CHANGELOG.
- Verified: `scripts/check.sh --qml` (760 passed, 3 skipped), `qmllint`
  on `GameSettings.qml`, `SectionBox.qml` and `DialogWindow.qml`, and
  offscreen shots (Details with the banner and the lock button, the
  Search Data footer and its three sources).
- Next: the maintainer's tag changes (the follow-up promised after the
  Tags lock), then the library import. The VNDB release picker sits in
  `TODO.md` before 1.0. Open follow-up: after the import, decide whether
  categories derive from tags, whether the tags get a filter/editor and
  whether a bulk download is worth it. Epic/GOG is 2.0, and so is the
  IGDB per-user credential review (`TODO.md`). The 1.0 visual pass, the
  packaging check, the shim removal and the release pass wait for the
  maintainer's release call.
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
