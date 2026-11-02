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
- Landed: eleven batches; the latest fixes GUI local-game correctness:
  the pre-launch menu names the real runtime (`Proton: <tool>`,
  `UMU: <Proton>`, `Wine: <binary>`, `Native`/`Steam Runtime`,
  `Runtime Not Set`), a Steam game's custom prefix resolves as the
  compatdata dir itself (sharing in the settings hint, empty field =
  Steam default), a local prefix under a `compatdata` folder is no
  longer Steam-owned, and the game list skips ProtonDB for local games.
  Before it: Steam-only assumptions dropped (`PROTON_LOG` only for
  proton/umu, notification never claims Proton for an unknown runtime,
  `--validate` note only for Steam games, Flatpak Steam detection,
  "Steam and local game launch wrapper" wording), winetricks skip for a
  custom Steam prefix, sanitized launcher state paths, config identity
  guards and the validation badge (`launcher.validate_issues()`
  error/warning levels, one labelled issue per tooltip line). Earlier
  batches: `CHANGELOG.md`.
- Verified: B5 targeted model tests and touched QML cases, full QML
  driver green, `--changed` and fast suite (537); offscreen screenshots
  covered the pre-launch runtime line (`Wine: wine`, no elision) and the
  Steam prefix hint at default (756 px) and minimum (612 px) width, no
  clipping and no QML warnings. Before it: B4 targeted tests (244),
  `--changed` and fast suite (533); B3 (85), `--changed` (88), fast suite
  (530); B2 (90), `--changed` (102), fast suite (529); B1 (185), fast
  suite (526). Venv refreshed after each merge. No real-display or real
  Steam library test.
- Next: the remaining audit-remediation batches B6–B8 — preset
  applicability for local runtimes, name/origin consolidation and
  docs — then the `TODO.md` "Deferred design review" items (runtime
  archives in a cache dir, the Steam Linux Runtime pick for local
  Wine/umu games and the issue badge in the card/icon views).
- Rebuild the `-git` package when the Steam path should follow `main`:
  `/usr/bin/tkarcade` is still post597 (`b4db456`, pre-overlay-fix).
- Nothing blocking.
