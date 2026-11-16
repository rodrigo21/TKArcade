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
- Landed: fifty-six batches. The latest capped the download paths:
  `artwork._get()` reads at most one byte past its limit (20 MB for
  images, 8 MB for JSON), a plain-http mirror is ignored, a runtime
  archive that fails to extract is quarantined as `.failed` (or deleted
  when TKArcade downloaded it), and tar links are rejected. Record:
  CHANGELOG.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh` (808 passed, 3 skipped, 1 deselected);
  no QML changed. The venv was refreshed after the merge.
- Next: batch D of the audit plan (`chore/launch-io`): one read in
  `graphics.py` and the full template-trim coverage in
  `tests/test_config.py`; then C1/C2
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
