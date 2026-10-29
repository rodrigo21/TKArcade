# Game taxonomy and terminology

Status: implemented (2026-10-27); runtime axis renamed (2026-10-29).

Goal: stop one field from answering two different questions. What a game
is (where it comes from, which system it is built for) and how it runs
(which runtime executes it) are separate axes; the library and the
settings window should name them the way players and other launchers do.

## Evidence

**Lutris** (checked in 0.5.x, installed locally) separates the axes in
the database, not only in the columns:

- `pga.db` `games` carries `platform`, `runner` and `service` as
  independent columns.
- `platform` is the target system (`Linux`, `Windows`, `ms-dos`, console
  names for emulated games); `runner` is the executor (`wine`, `linux`,
  `steam`, `dosbox`, `libretro`); `service` is the store the game came
  from (Steam, GOG, Epic).
- `platform` is derived from the runner when it is unknown
  (`runners/wine.py` declares `platforms = ["Windows"]`,
  `Runner.get_platform()` returns the first one); the service import
  maps the same way (`windows` → `wine`, `linux` → `linux`,
  `ms-dos` → `dosbox`).
- The sidebar groups by those axes: Library, Categories, Saved Searches,
  **Sources** (stores), **Runners**, **Platforms**. "Source" therefore
  means store, not "Steam vs local".

**Faugus** (checked in 1.x, installed locally) separates the runtime
from the platform even for native games:

- `runner` is `Linux-Native` or a Proton build; the origin is a separate
  launcher choice (`Linux Game`, `Steam Game`, `Epic Games`…).
- A `Linux-Native` game carries a `runtime` of its own
  (`umu-steamrt4`, `umu-sniper`, `umu-soldier`, `umu-scout`,
  `disable-runtime`), applied as `PROTONPATH=umu-…` or `DISABLE_UMU=1`.
  Steam Linux Runtime is orthogonal to the platform, not a property of
  Windows games.

## Decisions

TKArcade stores one axis and derives the others, like Lutris derives
`platform` from `runner`:

| Axis | Source | Values |
|---|---|---|
| Origin | derived from the AppID | `Steam`, `Local` |
| Platform | derived from the runtime | `Linux`, `Windows` |
| Runtime | stored | `proton`, `native`, `wine`, `umu` |
| Categories | stored | free tags |

The stored key was `[general] game_type`, which conflated "the game is a
Linux build" with "the game runs under Steam's Proton". It became
`[general] environment`, then `[runtime] type` (2026-10-29): the value is
the runtime that executes the game, and it sits next to the other launch
settings. The values stay the same so the launch path (`_game_argv`,
`_wrap_local_runtime`, `_runtime_paths` for `wine`/`umu`, winetricks)
does not change; only the name and the messages do.

| `runtime.type` | Origin | Runtime label |
|---|---|---|
| `proton` | Steam | Steam Proton |
| `native` | Steam | Steam Runtime |
| `native` | Local | Native (or `Steam Runtime (<code>)`) |
| `wine` | Local | Wine |
| `umu` | Local | UMU |

**Proton is Steam-exclusive.** It is Steam's own integration (compatdata,
compat tool, Steam's Linux Runtime), so a local game cannot use it; a
Windows build runs under plain Wine or through umu-run, which downloads
and executes its own Proton build. The reverse holds too: a Steam game
runs Steam's Proton or a native build, never Wine or UMU. `runtime_label()`
returns `""` for an invalid pairing and the launcher exits 18 with a
message naming the valid choices; the settings combo only offers the
origin's values.

**The free `platform` label is gone.** It was a string with no consumer
(no export, no filter, no launch effect) that only fed the Platform
column; it is removed instead of renamed, so the Platform column can
carry the derived system and categories cover "plays on the Deck". The
rejected alternative was keeping it as a "Device" label, which would
have added a second, functionless concept next to the axis that matters.

## Presentation

Library columns: 5 `Origin`, 7 `Platform` (derived), 8 `Runtime` (derived
label). Sorting and the column selector use the same three names; there
is no separate value filter. Settings: the runtime combo keeps the
origin-driven choices (`Native`, `Wine`, `UMU` for local games). The
"Environment Variables" section keeps its name: it is the `env.vars`
table, not the runtime.

## Compatibility

No migration shim (policy, pre-1.0): a config with `[general]
environment`, `game_type` or `platform` loads with those keys ignored,
so the runtime shows as "Not Set" and the launcher exits 18 until it is
chosen again. `[general] environment` is listed as a known key, so a
save drops it instead of preserving it as an unknown one. The CHANGELOG
entry marks the rename as **BREAKING**.

## Out of scope

Steam Linux Runtime for local Linux games (`soldier`, `scout`, `sniper`,
`steamrt4` through `umu-run`, the Faugus `runtime` combo) landed later
as `[runtime] steam_runtime` (see `TODO.md`); `runtime_label()` takes the
origin, so such a game labels as `Steam Runtime (<code>)`.
