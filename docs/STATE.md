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
- Landed: sixty-seven batches. The latest added the optional **Tags**
  column to the library table: hidden by default, placed before
  ProtonDB, showing the stored tag list comma separated, sortable by
  that text. `COLUMN_LAYOUT_VERSION` 2 gives a saved layout the column
  before ProtonDB, keeping its order and widths. Before it, **Set Tags…**
  in the selection menu and the persistent tag filter with Match Any.
- Closed as docs, no code: the metadata registry theme (C1–C8) left
  `TODO.md`. Its two open items described landed work, and
  `plans/metadata-provider.md` became `decisions/metadata-provider.md`,
  which keeps the C numbering the other records cite. The IGDB
  real-key wait moved to the 2.0 item. That batch passed
  `scripts/check.sh` (800 passed, 3 skipped) and is pushed.
- Verified: `scripts/check.sh --changed` and `scripts/check.sh --qml`
  (820 passed, 3 skipped) on the approved diff, plus the offscreen
  screenshot with Tags before ProtonDB. The venv was refreshed after
  the merge.
- Next: the Search Data tag selection: the preview Tags row opens the
  tag picker so individual provider tags are accepted or declined
  before Apply. The VNDB release picker sits in `TODO.md` before 1.0;
  the remaining tag follow-ups (merge policy, filter counts, picker
  search, import mapping, display polish) are there too. After the
  library import, decide whether categories derive from tags and
  whether a bulk download is worth it. Epic/GOG is 2.0, and so is the
  IGDB per-user credential review (`TODO.md`). The 1.0 visual pass, the
  packaging check, the shim removal and the release pass wait for the
  maintainer's release call.
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
