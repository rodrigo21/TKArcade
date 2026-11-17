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
- Landed: sixty-two batches. The latest fixed the header actions
  disappearing on a window clamped below the 1280 minimum: the Tags
  button carried a label in compact mode and pushed the whole actions
  row into Kirigami's overflow. It is icon-only with its siblings now,
  and the search filter yields to 120px instead of overrunning its
  slot. Regression case: `test_narrow_toolbar_with_tags_keeps_actions`.
  Before it, `[metadata] tags` became editable on Details (checkable
  picker, global `tags.toml`, `+N` summary, top-bar AND filter); record:
  `decisions/manual-tags.md`.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh --qml` (816 passed, 3 skipped) on the
  approved diff, plus offscreen screenshots at 700 and 1280 px. The venv
  was refreshed after the merge.
- Next: the library import. The VNDB release picker sits in `TODO.md`
  before 1.0. The tag follow-ups (manager, merge policy, match-any mode,
  preview selection, picker search, bulk edits, column, persistent
  filter, import mapping) are in `TODO.md`; after the import, decide
  whether categories derive from tags and whether a bulk download is
  worth it. Epic/GOG is 2.0, and so is the IGDB per-user credential
  review (`TODO.md`). The 1.0 visual pass, the packaging check, the shim
  removal and the release pass wait for the maintainer's release call.
- Deferred: the audit's #15 (launch parse) and #19 (role constants).
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
