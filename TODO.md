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
