# Runtime sources: one list and one default per kind

Status: decided (2026-11-06).

Landing record: the Wine list, the Prefix Base picker, the Proton
discovery and the graphics manager landed with this decision. Current
behaviour lives in `README.md` and `CHANGELOG.md`.

Goal: replace the free-text runtime fields in Preferences with the same
manager pattern everywhere — a list the user edits, one entry marked as
the default — and let the per-game dialog pick from that list instead of
asking for a path. The launcher keeps working without the GUI.

## Context

Preferences offered one text field per source: `wine_binary` (a path or a
name on `PATH`), `proton_dirs`, `dxvk_dirs`, `vkd3d_dirs`, `dxvk_repo`,
`vkd3d_repo`, plus a "Download Latest…" button per graphics layer and a
separate Manage Versions… dialog for the managed directory. That is six
string keys, three ways to reach a DXVK build and no way to say which one
a new game should use. The reference box has two Wine installs
(`/usr/bin/wine` from wine-staging, `/opt/wine-cachyos`), one system
Proton (`proton-cachyos-slr` under `/usr/share/steam/compatibilitytools.d`)
and two Proton-GE style tools in `~/.local/share/Steam/compatibilitytools.d`.

## Decision

### One list per kind, one default per kind

| Kind | List source | Editable | Default `""` means |
| --- | --- | --- | --- |
| Wine | `[ui] wine_versions` (system binaries, referenced) | add/rename/remove | Wine from `PATH` |
| Proton | discovered at runtime | no (read-only) | first discovered, system first |
| DXVK | managed dir + `runtimes/.external.json` | download/add/remove | newest installed |
| vkd3d-proton | managed dir + `runtimes/.external.json` | download/add/remove | newest installed |

Defaults: `[ui] wine_default`, `proton_default`, `dxvk_default`,
`vkd3d_default` hold the entry name; empty keeps the meaning above. A
removed or vanished entry resets its default instead of leaving a
dangling name. The keys live in `config.toml`, not in a sidecar, because
the launcher reads them without the GUI.

`proton_default` only preselects local games and umu. A Steam game keeps
Steam's own compatibility mapping: Steam decides.

### Wine

- The binary stays where it is. Nothing is copied or symlinked into a
  TKArcade directory: `wine_versions` holds `name=path` pairs joined by
  the platform path separator, and a missing path fails the launch with
  exit 14 instead of being rewritten out of the list.
- The name defaults to the directory that holds the build
  (`/opt/wine-cachyos/bin/wine` → `wine-cachyos`), made unique with a
  numeric suffix, and is renamed in the manager. A rename rewrites the
  `[runtime] tool` of every `wine` game that selected it.
- `PATH` is the implicit first row of the manager and cannot be removed.
- `[runtime] tool` stores the **entry name**. A raw path still resolves,
  so configs written before this decision keep launching and appear as
  the Custom row.
- The manager shows `wine --version` per row. The probe runs when the
  manager opens (cached by binary and mtime), never on the launch path.

### Proton

- Discovery, no configuration: `/usr/share/steam/compatibilitytools.d`
  (the system Proton, first), then every Steam library from
  `libraryfolders.vdf` — `steamapps/common/Proton*` and
  `compatibilitytools.d`.
- `proton_dirs` is removed. A Proton outside a Steam library is not
  discoverable; Steam's own `compatibilitytools.d` is the answer.
- One button, "Open Proton Manager": ProtonPlus first, ProtonUp-Qt when
  that is the only one installed, a menu with both when both exist.
  TKArcade installs no Proton itself.

### DXVK and vkd3d-proton

- One root, `data_home()/tkarcade/runtimes/<dxvk|vkd3d>`, one directory
  per version — the layout `graphics_versions()` already reads.
- Versions outside that root: the distro trees are scanned read-only
  (`/usr/share/dxvk`, `/usr/share/vkd3d-proton`, plus `/usr/local/share`),
  and **Add Folder…** registers any other path in
  `runtimes/.external.json` (a directory holding one version per
  subdirectory, or a single version directory). The files stay where they
  are; removing a row removes the reference, never the files. System and
  external builds have no Delete button.
- Downloads live only in the manager, and the release list loads when
  the dialog opens and when the source picker changes; there is no
  separate reload button. "Download Latest…", `dxvk_dirs`,
  `vkd3d_dirs`, `dxvk_repo` and `vkd3d_repo` go away. The source picker
  moves inside the manager as presets plus `Custom owner/repo`, stored
  per kind in `[ui] dxvk_source` / `vkd3d_source`.
- DXVK presets: official, `DXVK-Sarek`, and `DXVK-GPLAsync (legacy)` with
  a visible warning, because upstream discontinued it and only mirrors
  remain. vkd3d-proton presets: official and Custom.
- Provenance keeps working through `.sources.json`, and a version
  installed from a preset records the repository it came from.

### Preferences and the game dialog

The Runtime tab keeps **Prefix Base** with a folder picker next to the
text field, then one row per kind opening its manager. The per-game
dialog turns the Wine text field into a combo: the global default, the
managed entries, and a Custom row that reveals the old path field.

## Migration

| Stored | On load | On save |
| --- | --- | --- |
| `wine_binary` | becomes the first `wine_versions` entry, named from its path | key dropped |
| `dxvk_dirs` / `vkd3d_dirs` | paths appended to `.external.json` | keys dropped |
| `dxvk_repo` / `vkd3d_repo` | become `dxvk_source` / `vkd3d_source` | keys dropped |
| `proton_dirs` | ignored (discovery covers Steam-managed Protons) | key dropped |

A `[runtime] tool` holding a raw Wine path needs no rewrite: it resolves
as Custom and is named on the first save.

## Rejected

- **Copy or symlink Wine builds into a private directory** (the Lutris
  shape): duplicates gigabytes and splits ownership of the build.
- **A per-game repository override** for DXVK/vkd3d: one preset per kind
  keeps the download cache honest; a game-level fork would need its own
  cache key and a decision of its own.
- **A free-text Proton directory field**: every Proton the project cares
  about lives under Steam's own layout.

## Consequences

- Dropping `proton_dirs` is a real loss for a layout outside every Steam
  library; `README.md` says so in the same batch.
- The runtime schema changes: **BREAKING** entries in `CHANGELOG.md`.
  Tolerant readers stay until the 1.0 shim cleanup.
- `.external.json` reaches the launch path as a list of paths only;
  `json` is stdlib, so the stdlib-first invariant holds.

## Batches

1. Wine: keys, resolver, manager dialog, per-game combo, Prefix Base
   picker. Landed with this decision.
2. Proton: discovery, read-only list, Proton Manager button,
   `proton_default`, `proton_dirs` removed. Landed with this decision;
   the default preselects the game dialog and never rewrites a saved
   `[runtime] tool`.
3. DXVK/vkd3d: source presets in the manager, Add Folder, defaults,
   fields and `Download Latest…` removed, migration. Landed with this
   decision; presets resolve to `zeyadadev/DXVK-Sarek` and
   `Waim908/dxvk-gplasync-mirror`, and a vanished layer default falls
   back to the newest installed build while a version pinned by a game
   still warns.
4. Documentation sweep and handoff.
