# Current state

Ambient instruction: `opencode.json` lists this file, `docs/README.md`
(the document map) and `docs/GIT.md` (git rules) under `instructions`,
so every session reads them without being asked. Keep it short and
factual — history lives in `CHANGELOG.md` and git, deferred work in
`TODO.md`, document roles in `docs/README.md`. Refresh it with
`/handoff` before stopping mid-task.

- Branch: `main`, clean. The working tree carries only the maintainer's
  packaging churn in `packaging/arch/tkarcade-git/` (`PKGBUILD`
  `pkgver`, `optdepends` indentation and a lenient `check()`, plus an
  untracked `.SRCINFO`, never committed); `.qoder/` is git-ignored.
- Landed: eight batches; the latest sanitizes launcher state paths
  (per-game log, wrap sentinel and global-log token go through
  `safe_stem`) and treats a running record without a usable start time
  as dead. Before it: config identity guards (`config.save()` refuses a
  blank game ID, a local reset keeps `name` and `prefix_name`, and a
  cross-origin clone warns); before it: validation badge:
  `launcher.validate_issues()`
  tags each check as error (launch blocked or config unapplied) or
  warning (launch degraded), while `validate_game()`/`--validate` keep
  the flat strings; the table's name cell shows the worst level as a
  red error or orange warning icon whose tooltip lists the issues, one
  per line with an `Error:`/`Warning:` label and the keys verbatim (the
  Title Case rule is in `docs/DEVELOPMENT.md`). `TODO.md` keeps the
  badge for the card/icon views. Before it: missing
  installs (`missing_install()` catches a Steam game without an
  appmanifest/install folder — only when a Steam root exists — or a
  local executable that vanished; the issues filter, Validate Game and
  `--validate` exit 17, and the hamburger's "Remove Uninstalled
  Games..." confirms before deleting only those configs and reuses the
  leftover cleanup), then external runtime versions
  (`docs/decisions/external-runtimes.md`): DXVK/vkd3d come only from the
  Preferences directories (the Lutris and Flatpak-Lutris defaults are
  gone), each local Wine game picks `[graphics] dxvk_version` /
  `vkd3d_version` (empty = newest, a missing selection warns instead of
  falling back), and Proton installs require the `proton` launcher. Its
  settings follow-up reads Native, UMU, Wine, keys the Runtime rows on
  the kind (no Proton path leaking into the Wine field, no Detected
  Runtime row for Wine) and turns D3D12 into two mutually exclusive
  checkboxes with the version picker shown only while its layer is on.
  Earlier: the graphics-layers and settings-placement decisions and the
  Compat Tool filter (details in `CHANGELOG.md`).
- Verified: B2 passed its targeted tests (90), `--changed` (102) and the
  fast suite (529); B1 passed its targeted tests (185) and the fast
  suite (526). Before it, `scripts/check.sh --qml` 526 passed and
  offscreen screenshots covered the badge on error/warning/healthy rows,
  its colors and tooltips, at default and narrow widths, no QML
  warnings. Venv refreshed after each merge. No real-display or real
  Steam library test.
- Next: the remaining audit-remediation batches B3–B8 — Winetricks
  custom prefix, Steam assumptions, GUI local correctness, preset
  applicability, name/origin consolidation and docs — then the
  `TODO.md` "Deferred design review" items (runtime archives in a cache
  dir, the Steam Linux Runtime pick for local Wine/umu games and the
  issue badge in the card/icon views).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
