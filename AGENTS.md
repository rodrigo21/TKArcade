# AGENTS.md — instructions for AI coding agents on TKArcade

TKArcade is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-only launcher CLI (`tkarcade %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.

## Environment

- Python >= 3.12, Linux. Default flow is `uv` with system site packages:
  `uv venv --system-site-packages` (reuses Arch/CachyOS packages, never
  plain `venv`/`pip` into the system interpreter). Run checks with
  `.venv/bin/python`; `ruff` stays the system binary.
- Exception: `PKGBUILD check()` always uses system packages only
  (no uv in the chroot).
- The launcher (`src/tkarcade/launcher.py`, `config.py`, `backends/`,
  `proton.py`, `steam.py`, `xdg.py`, `nightlight_holder.py`) must stay
  **stdlib-only**: it runs on every game start. PySide6/vdf/jeepney are
  for GUI/helpers only.

## Verify before finishing

```bash
python3 -m pytest tests/ -q
ruff check src/ tests/
ruff format --check src/ tests/  # line-length 100, see pyproject.toml
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -c "..."  # GUI smoke
```

The suite must pass with and without `pytest-qt` installed: never
monkeypatch Qt globals at fixture scope (patch inside the test body so
teardown hooks see a healthy QApplication).

GUI changes need an offscreen screenshot check. Push each commit batch
created during build mode (the Arch package builds from git); never
rewrite pushed history or tags.

## Commits (one per area/theme)

- Message + `Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer.
- `AI-Model:` trailer comes from `.opencode-model` (gitignored) via the
  `scripts/git-hooks/commit-msg` hook (`core.hooksPath` is set repo-local).
- User-facing changes get a `CHANGELOG.md` entry under Unreleased, with
  explicit **BREAKING** notes.

## Kirigami/QML rules (hard-won, do not regress)

- Repeater models must stay JS arrays end to end: a QVariantList
  injected from Python (e.g. via setProperty) lays out at zero
  width on Qt 6.11. All QML writers build fresh JS arrays.
- Row clicks need modifiers (Ctrl/Shift multi-select): QEventPoint
  carries none, so rows use MouseArea (below the content, accepted
  Left|Right) instead of TapHandler.
- QML tests: never walk childItems() blindly (aborts on dead
  pooled/delegate wrappers) and never use findChildren for
  Repeater-nested items (QObject tree misses them). Navigate known
  structure only (objectName'd column roots + direct cells),
  match cells by parent modelData, and pump frames until delegates
  settle (Repeater columns instantiate asynchronously).

## Project policies (do not regress)

- No config migration/compat shims (pre-1.0): incompatible configs load
  as fresh built-ins.
- XDG Base Directory for all files; per-game TOML snapshots (full files,
  never sparse); `defaults.toml` is a new-game template only.
- New third-party deps need GPLv3-compatible licenses (MIT/BSD/
  Apache-2.0/PSF/LGPL). External tools via subprocess, never linked.
- Third-party recipes under `packaging/arch/` (linux-rt-upscaler*,
  pyproject-appimage) are synced copies from TKSteamLaunch: check
  drift with `diff -r` against it before tagging, copy the winner
  in a commit of its own.
- Rebuild `-git` locally to verify each batch, but never commit its
  `pkgver` churn (restore the PKGBUILD after); all PKGBUILDs change
  only on releases. On a feature branch the `-git` source pins that
  branch; at release time check every package for new versions,
  update every PKGBUILD and build them all.
- Flatpak Ludusavi cannot see Proton prefixes: always warn, never
  silently accept it.
- Exit codes are part of the CLI contract (10 no AppID, 12 pre-hook,
  13 missing exe, 14 missing prefix, 15 no display, 16 import/export,
  17 validation issues).
