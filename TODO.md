# TODO — deferred ideas

- [ ] Per-game display mode: save current resolution/refresh, apply the
  game's, restore afterwards (same save/restore pattern as nightlight).
  Providers with auto-detect: Plasma (`kscreen-doctor`), GNOME
  (`org.gnome.Mutter.DisplayConfig` over D-Bus), wlroots
  (`wlr-randr`/`kanshi`), X11 (`xrandr`), `off`.
- [ ] Per-game audio output: route to a chosen sink via `pactl`/`pw-cli`
  on launch, restore on exit.
- [ ] Review env presets against vendor docs (Mesa/NVIDIA semantics drift;
  verify `vblank_mode` / `__GL_SYNC_TO_VBLANK` values). Recurring: re-audit
  on every release tag (last: 2026-09-30 + installed-build checks).
- [ ] Block Internet per game (net namespace, unprivileged). DEFERRED for
  now: not cheap enough (LAN/achievements/Proton-under-userns risk matrix).
  Lighter alternative already shipped: `WINE_BLOCK_HOSTS` preset.
- [ ] vkBasalt successor: vkBasalt is unmaintained; evaluate forks or
  ReShade-on-Linux successors when mature (out for now).
- [ ] FPS cap field (MangoHud `fps_limit`) + libstrangle wrapper option for
  DX12 titles without overlay (`DXVK_FRAME_RATE` preset covers DX9-11 only).
- [ ] Lint expansion (decided 2026-10-06, after the first Kirigami GUI
  steps): enable the full Ruff rule set and fix everything it reports.
  Known first case: `stl_import.map_to_gameconfig` (mccabe 26 — rewrite
  as a table-driven mapping). Strong candidates: `C90`, `RET`, `A`, `N`,
  `SIM` (minus `SIM105`, our best-effort `try/except: pass` is deliberate),
  `LOG`, `ERA`, `FLY`, `RUF022`, `TCH`. Deliberately off (documented in
  `pyproject.toml`): `PLC0415` (lazy PySide imports isolate the launcher),
  `S` (subprocess is the whole project), `EM`/`TRY` (readable raise style),
  `T201` (print is the CLI interface), `SLF` (tests touch privates),
  `D`/`ANN` (churn, much later).
