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
- Landed: twelve batches; the latest makes Proton-only environment
  presets check local games: an UMU game matches the Proton it launches
  with, while Wine, native and UMU without a Proton are reported as a
  mismatch (Apply Anyway? still offered); Steam games with no
  compat-tool mapping keep offering every preset. Before it: GUI
  local-game correctness (pre-launch runtime label, a Steam game's
  custom prefix resolves as the compatdata dir itself with sharing in
  the settings hint, local prefixes under `compatdata` are not
  Steam-owned, the game list skips ProtonDB for local games), the
  Steam-only assumptions drop (`PROTON_LOG` only for proton/umu, the
  notification never claims Proton for an unknown runtime, `--validate`
  note only for Steam games, Flatpak Steam detection, "Steam and local
  game launch wrapper" wording), winetricks skip for a custom Steam
  prefix, sanitized launcher state paths, config identity guards and
  the validation badge (`launcher.validate_issues()` error/warning
  levels, one labelled issue per tooltip line). Earlier batches:
  `CHANGELOG.md`.
- Verified: B6 targeted tests (95), `--changed` (538) and the full QML
  driver (539, one batch abort re-ran in isolation green); B5 full QML
  driver green, fast suite (537) and offscreen screenshots (runtime
  line, Steam prefix hint at default and minimum width, no clipping);
  B4 targeted tests (244), fast suite (533); B3 (85/530); B2 (90/529);
  B1 (185/526). Venv refreshed after each merge. No real-display or
  real Steam library test.
- Next: the remaining audit-remediation batches B7–B8 — name/origin
  consolidation (no behaviour change) and docs/TODO — then the
  `TODO.md` "Deferred design review" items (runtime archives in a cache
  dir, the Steam Linux Runtime pick for local Wine/umu games and the
  issue badge in the card/icon views).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
