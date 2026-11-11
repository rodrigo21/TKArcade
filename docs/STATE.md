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
- Landed: forty-one batches. The latest has two: the provider registry
  with the Steam adapter (C1), and the Download Metadata preview (C2) —
  `Field | Current | New`, Apply fills empty fields, the **Replace
  existing values** switch overwrites, and the date is fillable. IGDB
  still waits on a Twitch app key.
- Verified: the preview by `scripts/check.sh --qml` (707 passed, 3
  skipped) plus an offscreen screenshot check of the dialog; the
  registry by the same suite (706/3) before it.
- Next: C3, the field locks (`[metadata] locked` and the game-dialog
  toggle), then the VNDB adapter with the candidate picker (C4), the
  PCGamingWiki adapter (C5), IGDB with the credential field and the
  provider menu (C6), IGDB artwork (C7) and online categories (C8); the
  library import follows. Epic/GOG is 2.0. The 1.0 visual pass, the
  packaging check, the shim removal and the release pass wait for the
  maintainer's release call.
- The Proton default is a dialog preselection only: a Steam game
  launches with Steam's own compat choice, and the manager says so.
- Process: the maintainer's rule (2026-11-06) is in `AGENTS.md` — no
  checks while iterating, one verification pass on the approved diff.
  Translations stay suspended (English-only new strings) until the 1.0
  pass restores the catalog.
- Open decisions: none block C3; C6 waits on the maintainer's Twitch
  application (client id/secret). `docs/plans/epic-gog-sources.md` is
  parked for 2.0 with its own four decisions (scope, discovery, launch,
  import UI).
- Nothing blocking.
