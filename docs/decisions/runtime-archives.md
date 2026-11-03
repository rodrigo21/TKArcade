# Runtime archives in a cache dir

Status: proposed (not landed).

Landing record: pending — this document freezes the design; it becomes a
landing record when the feature lands. Current behaviour lives in
`README.md`/`CHANGELOG.md`.

Goal: let TKArcade download the latest DXVK / vkd3d-proton release and
extract archives placed in a cache directory, without turning the
stdlib-only launcher into a downloader.

## Context

Versions today come only from `[ui] dxvk_dirs` / `vkd3d_dirs` in
Preferences: the user downloads, unpacks and points the directory list at
the result. `external-runtimes.md` deferred downloads and extraction and
kept the "archive support from a cache directory" item in `TODO.md`.

The official release formats set the constraints: DXVK publishes
`.tar.gz`; vkd3d-proton publishes `.tar.zst` only. The project floor is
Python 3.12 and the stdlib `compression.zstd` module arrived in 3.14, so
zstd support needs a dependency.

## Decision

- **Download is GUI-only and latest-only.** Each layer gets a "Download
  Latest…" action in Preferences: it queries the GitHub API for the latest
  release (`doitsujin/dxvk`, `HansKristian-Work/vkd3d-proton`), picks the
  preferred asset (`.tar.gz` for DXVK, `.tar.zst` for vkd3d-proton) and
  verifies the API's `sha256:` digest when present. There is no URL field.
- **Extraction is automatic.** Supported archives placed in the cache
  directory are extracted the next time the GUI scans the version list.
  Only the GUI scans; the launcher never unpacks anything.
- **zstd via PyPI `zstandard`** (BSD, GPL-compatible). Only the GUI-side
  helper imports it, and lazily, so the module stays importable without it.
- **The launcher stays stdlib-only.** Discovery gains one read-only path;
  download and extraction live in a module the launcher never imports.

## Proposed design (not implemented)

### Directories

- Managed installs: `data_home()/tkarcade/runtimes/<kind>` (new
  `xdg.runtimes_dir`), same shape as `default_prefix_base()`.
- Archive cache: `app_cache_dir()/archives` (new
  `xdg.archives_cache_dir`); holds downloads and user-dropped archives.

### Discovery

`runtimes.graphics_versions(kind, extra)` prepends the managed directory
to the configured ones through one private helper. The existing "a
directory without the DLL is a parent of version dirs" branch lists the
managed children, so the GUI list, the per-game dialog, launch and
`--validate` all see managed versions with no other call-site change.

### `src/tkarcade/runtime_archives.py` (new, imported only by `gui/model.py`)

- `latest_release(kind)`: GitHub `/releases/latest`, asset selection by
  suffix preference, returns name/url/size/digest. The URL opener is a
  parameter so tests never touch the network.
- `download_latest(kind, progress=None)`: streams to
  `<cache>/<asset>.part` with hash-while-writing and a size cap, verifies
  the digest, extracts, and unlinks the download only on success.
  Failures remove the partial file and return a status message.
- `sync_archives(progress=None)`: extracts every supported archive already
  in the cache (user-dropped files stay in place); an existing target is
  skipped.
- `extract_archive(kind, archive)`:
  - `.tar.gz` through `tarfile` with `filter="data"`; `.tar.zst` streamed
    through `zstandard.ZstdDecompressor().stream_reader` into a stream-mode
    `TarFile`; `.zip` through a manual member loop rejecting absolute,
    `..` and symlink entries, with member/size caps.
  - Exactly one top-level directory must hold `x64/<dll>`
    (`GRAPHICS_DLLS`); the version name is that directory's sanitized name
    (`dxvk-3.1.1`, `vkd3d-proton-3.1`).
  - Files land in a `.staging-…` directory under the kind root and the
    finished version directory moves into place with `os.replace`; stale
    staging directories are removed on the next sync.

### GUI

- `gui/model.py`: signals for progress/finished/versions-changed and
  daemon `threading.Thread` workers (same pattern as the file pickers and
  artwork fetch); one extraction worker guarded by a lock, gated by a
  cheap cache-directory listing, also triggered from `graphicsState()` so
  any version scan picks up pending archives without blocking the GUI.
- `PrefsDialog.qml`: one row per kind with a "Download Latest…" button, a
  busy indicator, a status label and a tooltip naming both directories.
  New strings get pt_BR translations through
  `scripts/refresh-translations.sh`; `.ts` and `.qm` ship together.

### Packaging (when implemented)

`zstandard` in `pyproject.toml` dependencies; `python-zstandard` in the
`-git` PKGBUILD `depends`; confirm the AppImage build bundles it.

## Tests when implemented

Qt-free unit tests for safe extraction (traversal, absolute paths, zip
symlinks, caps, missing top directory or DLL, idempotent skip, staging
cleanup, digest mismatch, success unlinking, missing `zstandard`), fake
API responses for asset selection and errors, managed-directory discovery
in `test_runtimes.py`, install/validate coverage, model-slot tests with
the helper patched in the test body, one QML dialog case, and an AST
check that the launcher module set imports neither `zstandard` nor
PySide6.

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
