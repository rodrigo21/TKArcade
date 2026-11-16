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
- Landed: fifty-four batches. The latest cleaned the Global Defaults
  editor: Notes and the Ludusavi game-name override (both per game) no
  longer appear there, `ludusavi.name_override` is stripped on save, and
  `_template_only()` trims identity/runtime/graphics/audio/debug/
  artwork/notes keys when the template is read too, so a hand-edited or
  pre-split `defaults.toml` cannot pre-fill a game. Status moved from
  Information to Game on Details, above State Tag; the template editor
  opens on Execution, and its Details tab carries a line naming what
  stays per game. Record: CHANGELOG.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh` (801 passed, 3 skipped),
  `scripts/check.sh --qml` (802 passed, 3 skipped), the config-defaults
  and settings QML cases, and offscreen shots of Details and the
  Global Defaults tabs. The venv was refreshed after the merge.
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
