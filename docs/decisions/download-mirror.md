# Download mirror

Status: decided (2026-11-07).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

## Problem

The DXVK and vkd3d-proton archives come from GitHub release assets, and
some networks cannot reach GitHub directly. The paste-an-archive-URL path
works around it one release at a time, but there is no way to keep the
release picker, the digest check and the update flow while fetching from
a proxy.

## Decision

1. `[ui] download_mirror` (Preferences → Runtime → Download Mirror) is an
   `https://` prefix prepended to every GitHub asset URL:
   `https://mirror/https://github.com/owner/repo/releases/download/...`,
   the ghproxy convention. Empty downloads direct.
2. Only asset downloads are rewritten. The GitHub API calls that list
   releases stay direct: a mirror proxies release files, and rewriting
   the API would add a second unsupported contract.
3. `install_from_url` never uses the mirror. The user typed that URL, so
   it is fetched as written.
4. The value is normalized on load and save: anything that is not
   `https://` becomes empty, so a typo cannot silently break downloads
   with a plain-HTTP or relative URL.
5. The SHA-256 digest from the GitHub API is still checked against the
   bytes the mirror returns, so a proxy can fail the check but cannot
   change what gets installed.

## Rejected alternatives

- **A per-layer mirror.** Two keys for one proxy, with no use case for
  fetching DXVK and vkd3d-proton through different hosts.
- **A hard-coded list of public proxies.** They appear and disappear;
  a user-supplied prefix is the smallest stable contract.
- **Rewriting the API too.** The GitHub API is not what a release-file
  proxy serves, and a broken API response would surface as a confusing
  "no release" error.
