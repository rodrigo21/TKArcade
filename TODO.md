# TODO — deferred ideas

- [ ] Per-game display mode: save current resolution/refresh, apply the
  game's, restore afterwards (same save/restore pattern as nightlight).
  Providers with auto-detect: Plasma (`kscreen-doctor`), GNOME
  (`org.gnome.Mutter.DisplayConfig` over D-Bus), wlroots
  (`wlr-randr`/`kanshi`), X11 (`xrandr`), `off`.
- [ ] Per-game audio output: route to a chosen sink via `pactl`/`pw-cli`
  on launch, restore on exit.
- [ ] Review env presets against vendor docs (Mesa/NVIDIA semantics drift;
  verify `vblank_mode` / `__GL_SYNC_TO_VBLANK` values).
