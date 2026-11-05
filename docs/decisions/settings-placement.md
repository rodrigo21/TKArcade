# Settings placement: Preferences and Global Defaults

Status: decided (2026-11-01).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: the two open audits — what in the Preferences window is truly
global, and which fields belong in the Global Defaults template — with
no setting moving between global and per-game.

## Decision

Settings have three homes, and a field keeps the one it already had:

1. **Global Preferences** — program state that applies to every game.
   All twelve fields stay global and the window groups them into
   `Interface`, `Tray`, `Artwork` and `Runtime` sections.
2. **Global Defaults** — origin-independent launch behaviour that a new
   game inherits until it is configured. No identity, runtime, layer,
   audio, artwork or selection memory.
3. **Per-game only** — identity, runtime and prefix choice, graphics
   layers, audio sink, artwork, notes and the active-profile memory;
   never written to `defaults.toml`.

| Setting | Home |
| --- | --- |
| Launch command preview, language | Preferences — `Interface` |
| Tray enable, icon style, minimize/close to tray, recent games, count | Preferences — `Tray` |
| SteamGridDB key, artwork source | Preferences — `Artwork` |
| Prefix base, Wine binary, Proton/DXVK/vkd3d directories | Preferences — `Runtime` |
| Environment variables; pre/post commands and timeout | Defaults — Commands |
| GameMode, Gamescope, MangoHud, RT upscaler | Defaults — Performance |
| Display, notifications, idle inhibit, network isolation, night light, Ludusavi | Defaults — Display/System |
| Pre-launch menu and timeout, custom command prefix, extra launch args | Defaults — General |
| Game name, categories, version/date/tag | Per game |
| Custom executable (override), working directory | Per game |
| `[runtime]`: type, tool, prefix, prefix name, fresh prefix, verbs, Steam runtime | Per game |
| `[graphics]`: DXVK, vkd3d-proton | Per game |
| `[audio]`: output sink | Per game |
| `[artwork]`, `[notes]` | Per game |
| `active_profile` | Per game |

## Why

- A preference changes the program for every game: it owns paths the
  launcher resolves, tray behaviour, the UI language and the artwork
  provider credential. A template only decides where a *new* game
  starts; it cannot make a choice on that game's behalf.
- The directories in Preferences are global locations. Each game still
  chooses its own runtime and prefix under them, so moving the base
  never rewrites a game.
- A template that pre-fills runtime, layers, audio or artwork would
  attribute choices to games the user never configured — and cloning a
  game would hide where the value came from.
- The SteamGridDB key is a credential and the artwork source picks the
  provider for the whole app; a per-game override is a path/AppID, not
  a provider switch.

## Behaviour today

- The Preferences window is three tabs (Interface, Artwork, Runtime)
  with one label column per tab and one shared Save/Cancel footer; the
  Tray rows live on the Interface page and disable when the tray is off.
- The Global Defaults dialog disables the Runtime tab with a one-line
  note (tab indices stay stable, so the other tabs do not move) and
  hides the General `Game` and System `Audio` sections, which hold only
  per-game fields.
- `save_defaults()` writes only the launch-behaviour sections; it drops
  `[metadata]`, `[runtime]`, `[graphics]`, `[audio]`, `[debug]`,
  `[artwork]`, `[notes]` and the General keys `name`,
  `custom_executable`, `launch_cwd`, `categories` and `active_profile`.
  An existing `defaults.toml` keeps them until the dialog is saved
  once.
- New games start from the trimmed template with no runtime set (the
  library shows Not Set and the launcher exits 18 until one is chosen);
  that is the intended explicit choice. The tarball,
  SteamTinkerLaunch and predecessor-config importers do the same: a
  Steam game gets the launcher's first-run prompt at its next launch,
  while a local game shows Not Set and exits 18 until one is chosen.
- `diff_vs_defaults()` now reports those per-game fields as differences
  from the template, which is what they are.

## Rejected alternatives

- **Move a setting between global and per-game.** Out of scope for the
  audit: no field changed owner, the template simply stopped carrying
  per-game fields.
- **Tabs in the Preferences window.** Four sections keep the single
  scroll and the content-driven window height; tabs would add clicks
  for twelve rows. Reversed (2026-11-05): the maintainer found the one
  scrolling page crowded, so the window now opens three tabs with a
  fixed height (see `CHANGELOG.md`).
- **Keep the template carrying the fields but ignore them at launch.**
  A config that stores a value it never uses is a trap for anyone
  editing the file by hand.
