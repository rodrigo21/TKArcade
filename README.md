# TKSteamLaunch

Minimal Steam launch wrapper (inspired by steamtinkerlaunch), in Python 3.12+.

GPLv3-or-later. See `LICENSE`.

## Install (local test with uv)

```bash
# one-time: install uv itself (no root needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

cd TKSteamLaunch
uv venv --system-site-packages .venv   # reuses system PySide6/vdf/jeepney
uv pip install --python .venv/bin/python --no-deps .
```

This installs the three entry points using the distro's Qt packages
(536 KB venv instead of ~650 MB of PyPI Qt):

| Command | Purpose |
|---|---|
| `tksteamlaunch` | Launcher used in Steam Launch Options |
| `tksteamlaunch-gui` | Settings GUI |
| `tksteamlaunch-nightlight-holder` | KDE NightLight inhibitor (spawned automatically) |

Run without installing: `PYTHONPATH=src python3 -m tksteamlaunch.gui.app`.
Delete `.venv/` to start over. A native Arch package (`PKGBUILD`) is planned.

## Steam usage

Set the game's Launch Options to one of:

```
tksteamlaunch %command%
tksteamlaunch --menu %command%     # pre-launch menu (Launch / Settings / Cancel)
```

The AppID resolves automatically from the Steam environment. Logs go to
`$XDG_STATE_HOME/tksteamlaunch/games/<appid>.log` (full) plus a one-line
entry per run in `launcher.log`.

## GUI guide

* **Configured Games** — double-click to edit; icons come from the Steam
  `librarycache`. `Add Game...` offers detected Steam games first.
* **General** — game type (auto-detected Proton/native), custom executable,
  custom command prefix (innermost wrapper, e.g. `zink-run`; a missing
  binary aborts the launch with exit 14), environment variables (table +
  bulk edit), pre-launch menu toggle, log file shortcut.
* **Pre/Post Commands** — programs run before/after the game (executable +
  arguments; optional shell mode; timeout; a failing pre-hook aborts
  with exit 12).
* **Performance** — Feral `gamemoderun` and CachyOS `game-performance`
  (mutually exclusive, Feral wins).
* **Gamescope & MangoHud** — wrappers plus gamescope presets and a
  MangoHud config picker (`MANGOHUD_CONFIGFILE`); create new configs
  from starter templates in your text editor.
* **Ludusavi** — save restore/backup around the game via `ludusavi wrap`
  (`--infer steam` or a name override, `--gui` prompts can decline per
  session). Flatpak Ludusavi warns: it cannot see Proton prefixes.
* **Night Light** — disables while playing, restores afterwards (KDE
  Plasma inhibitor, GNOME `gsettings`).
* **Global Defaults...** — template copied into new games; per-game
  `Reset to Global Defaults` drops local overrides. Game files always
  store complete snapshots; unknown keys are preserved.

## Config files (XDG)

* `$XDG_CONFIG_HOME/tksteamlaunch/games/<appid>.toml` — per-game snapshot.
* `$XDG_CONFIG_HOME/tksteamlaunch/defaults.toml` — new-game template only.
* `$XDG_STATE_HOME/tksteamlaunch/games/<appid>.log` and `launcher.log`.
* `$XDG_CACHE_HOME/tksteamlaunch/` — e.g. the ProtonDB tier cache.

Export/import everything with `tksteamlaunch --export FILE` /
`--import FILE` (or the GUI buttons).

## Exit codes

0 ok (the game's own code when it runs); 10 AppID not resolved;
11 empty game command; 12 pre-launch hook failed; 13 game executable
not found; 14 custom prefix binary not found; 15 display needed but
missing; 16 export/import failed; 17 validation issues found.
See `tksteamlaunch --help`.

## Troubleshooting

* **Game starts and quits instantly** — check the per-game log; a custom
  prefix or env var (e.g. vkBasalt) is the usual suspect. `--dry-run`
  prints the final command without running it.
* **Ludusavi does nothing** — the game must exist in Ludusavi (manifest
  or custom entry); use `Open Ludusavi...` and the `Check Coverage`
  button. The `wrap` exit code is always 0; the real game code is
  recovered internally and logged.
* **Night Light stuck off** — a leaked inhibitor holder may survive a
  crash: `pkill -f nightlight-holder`.
* **GUI looks unthemed under Steam** — the editor runs in a subprocess
  with Steam-runtime library paths filtered out; child stderr lands in
  the per-game log.

## Development

Launcher code (`launcher.py`, `config.py`, `backends/`, `proton.py`,
`steam.py`, `xdg.py`, `nightlight_holder.py`) stays stdlib-only — it
runs on every game start. PySide6/vdf/jeepney are for GUI/helpers only.
Dev tools come from system packages:

```bash
sudo pacman -S python-pytest ruff
python3 -m pytest tests/ -q
ruff check src/ tests/
ruff format --check src/ tests/  # line-length 100
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -c "..."  # GUI smoke
```

Breaking changes are recorded in `CHANGELOG.md` (config files have no
migration shims pre-1.0: incompatible files load as fresh built-ins).

Manual Plasma check for the NightLight holder (needs a session bus):

```bash
PYTHONPATH=src python3 -m tksteamlaunch.nightlight_holder & HPID=$!
sleep 2
qdbus6 org.kde.KWin /org/kde/KWin/NightLight \
  org.freedesktop.DBus.Properties.Get org.kde.KWin.NightLight inhibited  # true
kill -TERM $HPID  # inhibited returns to false
```

## AI assistance

This project is developed with AI assistance (OpenCode + Muse Spark),
reviewed by the maintainer. Every commit carries a `Co-Authored-By` trailer
plus an `AI-Model:` trailer with the model in use (from the gitignored
`.opencode-model` file); a local `commit-msg` hook (see
`scripts/git-hooks/`, enabled via
`git config core.hooksPath scripts/git-hooks`) adds both automatically.
Agent instructions live in `AGENTS.md`.
