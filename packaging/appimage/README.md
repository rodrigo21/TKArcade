# AppImage (unified entry)

`build.sh` produces `dist/TKSteamLaunch.AppImage` (git-ignored): the
single `tksteamlaunch` entry plus its Python runtime and
PySide6/vdf/jeepney wheels (~150-250 MB). Run without arguments (or
`--gui`) for the settings GUI; anything else runs the launcher, so
Steam Launch Options point at the file itself:

```
.../TKSteamLaunch.AppImage %command%
```

Notes and limits:

* Built with [pyproject-appimage](https://codeberg.org/JakobDev/pyproject-appimage)
  (`[tool.pyproject-appimage]` in the root `pyproject.toml`). `libappimage`
  is something else (the spec implementation) and is not needed.
* The bundle carries both faces: no arguments opens the settings
  GUI, anything else runs the launcher (same binary for Steam).
* External helpers (GameMode, Gamescope, MangoHud, Ludusavi,
  `protontricks`, `xdg-open`) stay on the host by design, same as the
  native packages.
* Running an AppImage needs FUSE (`dev/fuse`). Without it, extract and
  run directly: `./TKSteamLaunch.AppImage --appimage-extract` then
  `./squashfs-root/AppRun --version`.
* Smoke test after building: `--version`, `--help`, and one
  `--dry-run --appid <id>` against a configured game.
