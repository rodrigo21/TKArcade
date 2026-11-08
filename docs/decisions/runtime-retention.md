# Runtime retention and download trust

Status: decided (2026-11-07).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

`decisions/runtime-archives.md` and `decisions/runtime-manager.md` left
two policies open: nothing pruned the managed `<runtimes>` directory, and
downloads verified only the GitHub API digest. The caching half resolved
on its own: `_install_asset` deletes the archive after extracting it, so
only files the user dropped into the cache stay there, on purpose.

## Decision

1. Retention is automatic and fixed: each successful install, and every
   GUI scan, keeps the three newest managed builds per layer
   (`runtime_archives.KEEP_VERSIONS`, `prune_versions`). No preference:
   a knob nobody asked for would sit at its default forever.
2. Only builds recorded in `runtimes/.sources.json` are eligible, which
   means only builds TKArcade downloaded. A version dropped into the
   archive cache, an external folder or the distro tree is never pruned.
3. A prune never deletes the layer default or a version pinned by a game
   (`[graphics] dxvk_version` / `vkd3d_version`). Those survive even when
   older than the cut, so more than three builds may remain.
4. Deletion goes through `remove_version`, which refuses symlinks and
   paths outside the managed directory and rewrites the provenance file.
   The Removed games cleanup is unrelated: it touches per-game data.
5. No signature verification. The upstream repositories publish no
   `.sig`/`.asc` asset (checked against the latest DXVK and
   vkd3d-proton releases); the GitHub API SHA-256 digest is the strongest
   check available and is already enforced.

## Rejected alternatives

- **A `keep N` preference.** One more key and one more UI row for a
  policy with a sane fixed answer; the manual Delete stays for anything
  the prune keeps.
- **Pruning unrecorded builds too.** They are the user's files: a dropped
  archive or a distro package must never disappear because a download
  added a fourth build.
