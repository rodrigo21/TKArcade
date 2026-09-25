# AGENTS.md — instructions for AI coding agents on TKSteamLaunch

TKSteamLaunch is a minimal Steam launch wrapper: per-game TOML configs,
a stdlib-only launcher CLI (`tksteamlaunch %command%`) and a PySide6 GUI.
License: GPL-3.0-or-later.

## Communication

- Chat with the maintainer in Portuguese; code, docs, comments, commit
  messages and GUI strings in English.
- Short, factual, no superlatives. Surface disagreements honestly.

## Environment

- Python >= 3.12, Linux. Dev tools from CachyOS/Arch system packages
  (`sudo pacman -S python-pytest ruff`) — never create venvs.
- The launcher (`src/tksteamlaunch/launcher.py`, `config.py`, `backends/`,
  `proton.py`, `steam.py`, `xdg.py`, `nightlight_holder.py`) must stay
  **stdlib-only**: it runs on every game start. PySide6/vdf/jeepney are
  for GUI/helpers only.

## Verify before finishing

```bash
python3 -m pytest tests/ -q
ruff check src/ tests/
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -c "..."  # GUI smoke
```

GUI changes need an offscreen screenshot check. Never `git push`;
never rewrite pushed history or tags.

## Commits (one per area/theme)

- Message + `Co-Authored-By: OpenCode <noreply@opencode.ai>` trailer.
- `AI-Model:` trailer comes from `.opencode-model` (gitignored) via the
  `scripts/git-hooks/commit-msg` hook (`core.hooksPath` is set repo-local).
- User-facing changes get a `CHANGELOG.md` entry under Unreleased, with
  explicit **BREAKING** notes.

## Project policies (do not regress)

- No config migration/compat shims (pre-1.0): incompatible configs load
  as fresh built-ins.
- XDG Base Directory for all files; per-game TOML snapshots (full files,
  never sparse); `defaults.toml` is a new-game template only.
- New third-party deps need GPLv3-compatible licenses (MIT/BSD/
  Apache-2.0/PSF/LGPL). External tools via subprocess, never linked.
- Flatpak Ludusavi cannot see Proton prefixes: always warn, never
  silently accept it.
- Exit codes are part of the CLI contract (10 no AppID, 12 pre-hook,
  13 missing exe, 14 missing prefix, 15 no display, 16 import/export,
  17 validation issues).
