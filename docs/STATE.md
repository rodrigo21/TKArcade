# Current state

Ambient instruction: `opencode.json` lists this file under
`instructions`, so every session reads it without being asked. Keep it
short and factual — history lives in `CHANGELOG.md` and git, deferred
work in `TODO.md`. Refresh it with `/handoff` before stopping mid-task.

- Branch: `feat/local-appid-slug` (off `main`), one commit, waiting for
  the maintainer to test before the squash merge. Uncommitted here: only
  the maintainer's `pkgver` in `packaging/arch/tkarcade-git/PKGBUILD`.
- Landed on the branch: local AppIDs use a real slug (`config.local_slug`,
  `local_id_base`, hash fallback `local_name_hash` for names with no
  ASCII letters), plus a one-shot idempotent `config.migrate_local_ids()`
  that runs at GUI startup and through `tkarcade --migrate-ids`. It moves
  config, profiles, artwork, grids, per-game log, winetricks state,
  history lines and `donor_appid` refs, pins an existing prefix through
  `[runtime] prefix_name` instead of renaming the directory, and only
  touches IDs that are not slug-clean (`clean_local_id`), so clone
  targets and Steam IDs stay as they are.
- Verified: fast suite 421 passed, 1 deselected; ruff/format clean. The
  QML driver was not re-run for this change (no QML touched; the model
  only gained a startup migration call).
- Next concrete step: the maintainer tests the migration on the real
  config, then the branch is squash-merged. After that, session 2 of the
  TODO plan: settings reorg (merge Game+Launch tabs, unify
  `[proton]`/`[runtime]`, option B — breaking is fine).
- Then: session 3 — metadata fields (version/date/tag, name suffixes,
  never in the AppID), categories redesign and dropping the Category
  column from the library list.
- Open decisions: none for the slug work. Still open from before: for the
  Steam Linux Runtime item, (a) refuse when the runtime is not in
  `~/.local/share/umu/` (exit 14) or let umu download it; (b) label
  "Steam Runtime" or "Steam Runtime (sniper)".
- Nothing blocking.
