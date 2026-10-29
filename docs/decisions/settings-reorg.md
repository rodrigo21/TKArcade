# Settings reorg (session 2)

Status: landed. Breaking config changes are allowed
(policy: no shims pre-1.0), so the old keys are dropped and the
CHANGELOG says which ones and what replaces them.

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problems

1. `Game` and `Launch` tabs split per-game identity from the rest of
   the launch setup; the two sections fit in one screen.
2. The tab named `Environment` holds env vars, while
   `[general] environment` (proton/native/wine/umu) is the runtime
   choice. Same word, two meanings.
3. `Compatibility` mixes the runtime choice, the graphics layers and
   the Proton debug switches.
4. `[proton]` and `[runtime]` are two stores for one feature: prefix
   location (`wine_prefix` vs `prefix_dir`/`prefix_name`), tool
   selection (`wine_version` vs `proton_path`/`wine_binary`) and
   `winetricks_verbs`. Which section applies is decided by the
   environment, not by the user.

## Tabs (7, down from 8)

| Tab | Content |
| --- | --- |
| `Game` | Game (name/appid), Profile, Launch (exe, custom command prefix, args, working dir, pre-launch menu) |
| `Runtime` | Runtime selector (proton/native/wine/umu), tool selection, prefix, winetricks verbs, fresh prefix, DXVK/vkd3d, Proton log and WINEDEBUG |
| `Commands` | The per-game environment variable table plus the Pre/Post commands (renamed from `Environment`; the old name collided with the runtime choice) |
| `Performance` | Game Mode, MangoHud, RT Upscaler, Gamescope |
| `Display` | Display mode |
| `System` | Notifications, idle suspend, night light, network, audio, Ludusavi |
| `Artwork/Notes` | Unchanged |

`Compatibility` disappears: its content moves to `Runtime` (runtime,
prefix, graphics layers and debug), so `Performance` keeps only the
wrapper tools and the RT upscaler.

## Config (one `[runtime]` section)

| Old | New |
| --- | --- |
| `[proton] fresh_prefix` | `[runtime] fresh_prefix` |
| `[proton] winetricks_verbs`, `[runtime] winetricks_verbs` | `[runtime] winetricks_verbs` |
| `[proton] wine_prefix` (Steam: `STEAM_COMPAT_DATA_PATH`) and `[runtime] prefix_dir` (local: `WINEPREFIX`) | `[runtime] prefix` — one key, meaning depends on the runtime (Steam compatdata dir vs the local prefix **base**; the WINEPREFIX is `<base>/<folder>`, see `prefix-name.md`) |
| `[runtime] prefix_name` | `[runtime] prefix_name` (local only) |
| `[proton] wine_version` (Steam compat tool), `[runtime] proton_path` (umu `PROTONPATH`), `[runtime] wine_binary` | `[runtime] tool` — one key, interpreted per environment: Steam compat tool name, umu `PROTONPATH`, or the Wine binary |
| `[graphics] dxvk`, `[graphics] vkd3d` | unchanged (move into the `Runtime` tab, not into `[runtime]`) |
| `[debug] proton_log`, `[debug] winedebug` | unchanged |

`[proton]` disappears; old configs lose it (and the duplicated keys).

## Files

- `config.py`: `ProtonConfig` removed, `RuntimeConfig` gains `tool`,
  `prefix`, `fresh_prefix`; `SECTION_KEYS` updated; `to_toml_dict` /
  `_build` / `defaults_dict` follow.
- `launcher.py`: `cfg.proton.*` → `cfg.runtime.*`; `runtime` dict built
  from the single `tool` key (Steam compat tool / `PROTONPATH` / wine
  binary).
- `gui/model.py`: `to_fields` / `apply_fields` (`winePrefix`,
  `wineVersion`, `runtime_*` collapse into `runtime_prefix`,
  `runtime_tool`), prefix helpers, applyWineVersion, ensure/clear prefix.
- `stl_import.py`: verbs into `[runtime]`.
- `GameSettings.qml`: tab bar and sections per the table above; the
  Steam/local widgets share the prefix and tool fields.
- Tests: `test_config.py`, `test_backends.py`, `test_stl_import.py`,
  `test_kirigami_model.py`, `kirigami_qml_cases.py` (tab constants and
  every `ptVerbs`/`winePrefix`/`runtime_*` case).
- `CHANGELOG.md` (BREAKING), `README.md`, `translations/*.ts`, man page
  if it names the keys.

## Verify

`scripts/check.sh`, `scripts/check.sh --qml`, offscreen screenshot of
the new tab bar and the merged `Game` tab.
