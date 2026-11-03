# Runtime archives in a cache dir

Status: landed (2026-11-03).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: let TKArcade download the latest DXVK / vkd3d-proton release and
extract archives placed in a cache directory, without turning the
launcher into a downloader.

## Context

Versions come from the managed directory plus `[ui] dxvk_dirs` /
`vkd3d_dirs` in Preferences: the user downloads, unpacks and points the
directory list at the result. `external-runtimes.md` kept the launcher
read-only and deferred downloads and extraction to this decision.

The official release formats set the constraints: DXVK publishes
`.tar.gz`; vkd3d-proton publishes `.tar.zst` only. The project floor is
Python 3.12.

## Decision

- **Download is GUI-only and latest-only.** Each layer gets a "Download
  Latest…" action in Preferences: it queries the GitHub API for the latest
  release (`doitsujin/dxvk`, `HansKristian-Work/vkd3d-proton`), picks the
  preferred asset (`.tar.gz` for DXVK, `.tar.zst` for vkd3d-proton) and
  verifies the API's `sha256:` digest when present. There is no URL field.
- **Extraction is automatic.** Supported archives placed in the cache
  directory are extracted the next time the GUI scans the version list.
  Only the GUI scans; the launcher never unpacks anything.
- **zstd is stdlib-first.** `compression.zstd` covers Python 3.14+; the
  PyPI `zstandard` package (BSD, GPL-compatible) is the fallback below
  3.14 through the `zstandard; python_version < '3.14'` marker. The
  import stays lazy, so the module and the GUI start without either.
- **The launcher never downloads or unpacks.** Discovery gains one
  read-only path; download and extraction live in a module the launcher
  never imports.

## Design (as landed)

### Directories

- Managed installs: `data_home()/tkarcade/runtimes/<kind>`
  (`xdg.runtimes_dir`), same shape as `default_prefix_base()`.
- Archive cache: `app_cache_dir()/archives` (`xdg.archives_cache_dir`);
  holds downloads and user-dropped archives.

### Discovery

`runtimes.graphics_versions(kind, extra)` prepends the managed directory
to the configured ones through one private helper. The existing "a
directory without the DLL is a parent of version dirs" branch lists the
managed children, so the GUI list, the per-game dialog, launch and
`--validate` all see managed versions with no other call-site change.
Managed wins on equal names because its root comes first.

### `src/tkarcade/runtime_archives.py` (imported only by `gui/model.py`)

- `latest_release(kind, opener=None)`: GitHub `/releases/latest`, asset
  selection by suffix preference, returns name/url/size/digest. The URL
  opener is a parameter so tests never touch the network.
- `download_latest(kind, opener=None, progress=None)`: streams to
  `<cache>/<asset>.part` with SHA-256 while writing, a 512 MiB cap and
  the API size when present; verifies the `sha256:` digest, moves the
  archive into place, extracts, and unlinks it only on success.
  Failures remove the partial file and return a status message.
- `sync_archives(progress=None)`: removes stale `.staging-…` directories,
  extracts every supported archive already in the cache (user-dropped
  files stay in place; an existing target is skipped) and returns the
  newly installed version names; failures go through `progress`.
- `extract_archive(archive, kind="")`: `.tar.gz` through `tarfile` with
  `filter="data"`; `.tar.zst` streamed into a stream-mode `TarFile`;
  `.zip` through a manual member loop rejecting absolute paths, `..` and
  symlink entries, with 20k-member and 1 GiB extracted-size caps.
  Exactly one top-level directory must hold `x64/<dll>`
  (`GRAPHICS_DLLS`); the version name is that directory's sanitized name
  (`dxvk-3.1.1`, `vkd3d-proton-3.1`). Files land in a `.staging-…`
  directory under the managed root and the finished version directory
  moves into place with `os.replace`.
- `supported(name)` and `ArchiveError` complete the surface.

### GUI

- `gui/model.py`: `archiveProgress`/`archiveFinished`/`archivesChanged`
  signals and daemon `threading.Thread` workers (same pattern as the
  file pickers and artwork fetch); one extraction worker guarded by a
  lock, gated by a cheap cache-directory listing, also triggered from
  `graphicsState()` so any version scan picks up pending archives
  without blocking the GUI.
- `PrefsDialog.qml`: one row per kind with a "Download Latest…" button,
  a busy indicator, a status label and a tooltip naming both
  directories. `GameSettings.qml` refreshes the graphics pickers on
  `archivesChanged`. New strings got pt_BR translations through
  `scripts/refresh-translations.sh`; `.ts` and `.qm` ship together.

### Packaging

`zstandard; python_version < '3.14'` in `pyproject.toml`. Arch ships
Python 3.14, so the `-git` PKGBUILD needs no `python-zstandard`; the
AppImage build takes its dependencies from pyproject.

## Tests

Qt-free unit tests for safe extraction (traversal, absolute paths, zip
symlinks, caps, missing top directory or DLL, idempotent skip, staging
cleanup, digest mismatch, success unlinking, missing zstd backend), fake
API responses for asset selection and errors, managed-directory
discovery and precedence in `test_runtimes.py`, model-slot tests with
the helper patched in the test body, one QML dialog case, and an AST
check that the launcher module set imports neither `zstandard` nor
`runtime_archives` nor PySide6.

## Risks and limits

- GitHub API rate limit (60/h unauthenticated): surface the error, no
  retries.
- Trust model: HTTPS, API sha256 digest, `filter="data"`, zip traversal
  guard, size/member caps, staging directory. No signature verification.
- The same version name in the managed and a configured directory appears
  twice (different paths); selection by name resolves managed first.
- No retention policy for old managed versions; the user deletes them.
- Automatic extraction runs only when the GUI scans; nothing happens at
  launch.

## Out of scope

- Proton/Wine downloads, an arbitrary URL field, signature verification,
  retention/cleanup policy, mirrors.
