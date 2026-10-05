# AppImage (unified entry)

`build.sh` produces `dist/TKArcade-<version>.AppImage` (git-ignored): the
single `tkarcade` entry plus its Python runtime and
PySide6/vdf/jeepney wheels (~150-250 MB). Run without arguments (or
`--gui`) for the settings GUI; anything else runs the launcher, so
Steam Launch Options point at the file itself:

```
.../TKArcade-<version>.AppImage %command%
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
  run directly: `./TKArcade.AppImage --appimage-extract` then
  `./squashfs-root/AppRun --version`.
* The bundle carries our `.desktop` file (needed by appimagetool
  validation) alongside `.DirIcon`; both come from the repo.
* System theme plugins (Breeze, qt6ct) cannot load against the bundled
  Qt: inside an AppImage the GUI defaults to stock Fusion unless
  `QT_STYLE_OVERRIDE` is set. Native packages use the system Qt and
  follow the desktop theme.
* Smoke test after building: `--version`, `--help`, and one
  `--dry-run --appid <id>` against a configured game.
