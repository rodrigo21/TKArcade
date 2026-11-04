# Runtime version manager

Status: decided (2026-11-04).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: install more than the latest official DXVK/vkd3d-proton release,
keep several versions side by side (including unofficial builds such as
DXVK-Sarek), record where each one came from, and delete the ones no
longer wanted — without moving any of that into the launcher.

## Context

`external-runtimes.md` kept the launcher read-only and per-game selection
by version name. `runtime-archives.md` added GUI-only latest-release
downloads into `data_home()/tkarcade/runtimes/<kind>` plus automatic
extraction of archives dropped into the cache. Both left four gaps: no
way to pick an older release, no unofficial source, no provenance label
and no way to delete a managed version from the GUI.

Multi-version coexistence and per-game selection already worked
(`runtimes.graphics_versions` lists every version directory, `[graphics]
dxvk_version` / `vkd3d_version` pick one by name), so the manager only
had to fill those four gaps.

## Decision

- **Any release, not only the latest.** `runtime_archives.releases`
  lists `/releases?per_page=30` for a layer, skipping drafts and releases
  without a matching asset; `download_release` installs the picked one.
- **Unofficial builds through a per-kind repository.** `[ui] dxvk_repo`
  and `[ui] vkd3d_repo` take a GitHub `owner/repo`; empty keeps the
  official `doitsujin/dxvk` / `HansKristian-Work/vkd3d-proton`. The
  release list, digest check and extraction are identical for a fork.
- **A pasted URL is the escape hatch.** `install_from_url` downloads a
  direct archive URL with the same stream, size caps and extraction
  checks. There is no release metadata, so no digest is verified.
- **Provenance is recorded, not derived.** `<runtimes>/.sources.json`
  maps `<kind>/<name>` to origin (`github`/`repo`/`url`), repository, tag,
  URL and timestamp. It is GUI-only bookkeeping: the launcher never reads
  it, it survives a missing or corrupt file, and entries whose directory
  is gone drop out on read.
- **Retention is manual.** The manager deletes one managed version after
  a confirmation; nothing prunes automatically. Only children of
  `runtimes_dir()/<kind>` are deletable (resolved path check, no
  symlinks, no parent escape); configured `dxvk_dirs`/`vkd3d_dirs` and
  Steam/umu runtimes stay read-only.
- **The launcher stays read-only.** No new module on the launch path; the
  AST guard that forbids `runtime_archives` in the launcher already
  covers the new functions.

## Design

### `src/tkarcade/runtime_archives.py`

- `_repo(kind, repo)` validates `owner/repo` (`[A-Za-z0-9._-]+` per part)
  and falls back to the official repository.
- `releases(kind, opener=None, repo="")` returns
  `{name, url, size, digest, tag, prerelease}` rows, newest first.
- `_install_asset` is the one download/verify/extract path, shared by
  `download_latest`, `download_release` and `install_from_url`; it records
  provenance after extraction and unlinks the archive only on success.
- `remove_version(kind, name)` deletes one managed directory and forgets
  its manifest entry; the message is `""` on success.
- `sources()` / `_write_sources()` / `_record_source()` own the manifest,
  written through `.part` + `os.replace`.

### GUI

- `gui/model.py`: `runtimeReleases` signal (kind, rows, error), slots
  `runtimeVersions`, `fetchRuntimeReleases`, `installRuntimeRelease`,
  `installRuntimeFromUrl`, `removeRuntimeVersion`. Installs reuse the
  existing per-layer busy set, the serialized work lock and the
  `archiveProgress`/`archiveFinished`/`archivesChanged` signals.
- `RuntimeManagerDialog.qml` (a `DialogWindow`, per `QML-NOTES.md`): the
  managed versions with their source label and a Delete confirmation, a
  release picker, a URL field, a busy indicator and a status line.
  `PrefsDialog.qml` adds the two repository fields and a Manage Versions…
  button per layer.

## Why

The gaps were about *which* build and *where it came from*, not about
discovery or per-game selection, which already worked. Keeping the
manager GUI-only preserves the launcher policy from
`external-runtimes.md`; keeping deletion manual avoids a retention policy
that would silently remove a build a game still selects (the launch
warning already covers that case).

## Rejected alternatives

- **Auto-retention (`keep N`).** A new key plus pruning logic that deletes
  builds the user may still want; the manager makes manual deletion one
  click.
- **Only a URL field, no repository preference.** Works once, but every
  fork update needs a fresh URL; a repository preference keeps the
  release list usable for DXVK-Sarek.
- **Listing configured directories in the manager.** Half the rows would
  have no Delete action, and the dialog would imply ownership of paths
  TKArcade only reads.
- **Reading the manifest in the launcher.** Provenance is advisory UI
  data; the launch path stays read-only and cheap.

## Risks and limits

- A pasted URL has no digest: HTTPS, the suffix check, the size caps and
  the single-version-directory rule are the whole trust model.
- GitHub lists 30 releases per request and rate-limits unauthenticated
  calls at 60/h (two dialogs open = two requests); the error surfaces in
  the dialog, no retry.
- A fork without the expected asset suffix shows an empty release list.
- Deleting a version a game selects makes that launch warn "not
  installed" (`--validate` too); nothing rewrites game configs.
- A hand-deleted directory leaves a stale manifest entry only until the
  next `sources()` call prunes it.

## Tests

Qt-free cases for the release list (draft and asset filters, API errors),
configured-repository selection, invalid repositories, single-release
install, URL install (basename naming, suffix refusal, missing kind),
deletion (managed only, traversal, symlink, manifest cleanup) and
manifest tolerance; config cases for the repository cleaner and the
roundtrip; model-slot cases for listing, installing and deleting; and one
QML case that opens the manager from Preferences and checks the managed
row and the loaded release.
