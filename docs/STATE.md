# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, pushed, clean. The working tree carries only the
  maintainer's packaging churn in
  `packaging/arch/tkarcade-git/PKGBUILD`, never committed.
- Landed: twelve batches. Prefix/config/winetricks guards, sanitized
  paths, background GUI probes (no freezes), custom `WINEDEBUG`,
  uppercase IDs, shared helpers and 9 redundant tests removed, the
  runtime version manager (`docs/decisions/runtime-manager.md`), the
  tabbed Preferences window with its header button, the Manage Versions
  release combo fix, the hamburger rework, and the artwork sources batch
  (per-game `[artwork] provider`, hand-typed Artwork Source AppID that
  wins over the game's own art, SteamGridDB name lookup for local games,
  Steam-first icon chain with a one-time stale-icon drop, Fetch/Clear on
  the AppID row). The commit rule is now "commit only after the diff is
  approved" (`docs/GIT.md`).
- Verified: `scripts/check.sh` 635 passed and `scripts/check.sh --qml`
  636 passed; real API checks (2399420 keeps the 32x32 Steam client
  icon, 3321460 keeps the 256 PNG) and offscreen screenshots of the
  Artwork tab at 800/1280; venv refreshed after the merge.
- Next: the icon from the game executable for local Windows games, then
  the artwork preview thumbnails, then the deferred research and release
  items (`TODO.md`).
- Open decisions: none blocking; `docs/decisions/artwork-sources.md`
  covers the artwork work and `docs/decisions/artwork-provider.md`
  carries a **Reversed** note.
- Nothing blocking.
