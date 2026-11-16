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
- Landed: fifty-five batches. The latest hardened the file writers:
  `write_atomic()` no longer sweeps another process's live temp, every
  artwork sidecar write goes through it, a `200` body that is not an
  image is rejected before it fills a slot, and the IGDB token cache is
  `0600` in a `0700` directory. Record: CHANGELOG.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh` (804 passed, 3 skipped, 1 deselected);
  no QML changed. The venv was refreshed after the merge.
- Next: batch B of the audit plan (`fix/network-archive-limits`): read
  cap in `artwork._get()`, https-only mirror, downloaded archive removed
  on a failed extraction, tar links rejected, invalid user drop renamed
  `.failed`; then batch D (launch I/O + template-trim test), then C1/C2
  (GUI model and artwork slot). After the audit: the maintainer's tag
  changes (the follow-up promised after the Tags lock), then the library
  import. The VNDB release picker sits in `TODO.md` before 1.0. Open
  follow-up: after the import, decide whether
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
