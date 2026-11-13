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
- Landed: fifty-one batches. The latest fixed Fetch Artwork end to end.
  IGDB searches the title when no id is stored, takes an exact match or
  the provider-tagged picker, and writes the resolved id to
  `[metadata] igdb_id` plus the cache sidecar; a source AppID's IGDB game
  is never written to the local game, and `igdbResolved` keeps the dialog
  draft in step so a later Save cannot erase it. Fetch drops the game's
  own Clear mark as well as the source AppID's, so a sourced tile comes
  back. Every game Save fills missing artwork. Preferences separates the
  default **Artwork Source** from **API Keys**, and IGDB remains the
  stored source instead of falling back to Steam. Record: CHANGELOG.
- Verified: `scripts/check.sh --qml` (773 passed, 3 skipped), `qmllint`
  on `GameSettings.qml` and `PrefsDialog.qml`, and an offscreen shot of
  the Artwork preferences. The QML age-rating case now scrolls its row
  into view; it failed on the pre-batch HEAD because the row sat below
  the Details viewport.
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
