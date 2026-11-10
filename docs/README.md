# Documentation map

What each document is for and where the source of truth lives.

| Question | Document |
| --- | --- |
| What TKArcade does and how to use it | `README.md` (repository root) |
| What changed, and when | `CHANGELOG.md` and the git history |
| Current config keys and launch behaviour | `README.md` ("Local games", "Config files") and `src/tkarcade/config.py` |
| Standing project decisions | `POLICIES.md` |
| Open work | `TODO.md` |
| Branch, commit, merge and push rules | `GIT.md` |
| Current session state (ambient) | `STATE.md` |
| QML/Kirigami rules learned the hard way | `QML-NOTES.md` |
| Dev environment, tests, packaging, releases | `DEVELOPMENT.md` |
| Why a landed design is the way it is | `decisions/` (frozen landing records) |
| Manual display checks before a release | `runbooks/real-display-checks.md` |

## Rules

- `TODO.md` is the open list only. Finished work goes to `CHANGELOG.md`
  and git; standing decisions go to `POLICIES.md`.
- `STATE.md`, `GIT.md` and this map are the ambient documents (injected
  through `opencode.json`), so an agent always knows where each answer
  lives and which git rules apply without searching: keep them short
  and refresh `STATE.md` with `/handoff`.
- `AGENTS.md` routes by trigger ("before touching X, read Y"); this map
  is the exhaustive index behind it.
- `decisions/` are frozen landing records: they describe the state at
  landing, not necessarily today's behaviour. Correct them only when
  the rationale or the historical record is wrong; current behaviour
  belongs in `README.md`/`CHANGELOG.md`.
- `runbooks/` are procedures, not designs; keep them executable.
- A change that makes a document wrong updates it in the same commit.
  `tests/test_docs.py` enforces the rules above: every document must be
  listed here, `TODO.md` cannot carry a finished item, every decision
  keeps its landing banner, and nothing may point at the retired plans
  directory (its content moved to `decisions/` and `runbooks/`).

## Decisions

- `decisions/game-taxonomy.md` — Origin/Platform/Runtime axes and the
  `[runtime]` key.
- `decisions/settings-reorg.md` — the seven-tab game dialog and the
  merged runtime config.
- `decisions/prefix-name.md` — local prefix base and `<base>/<folder>`
  resolution.
- `decisions/network-isolation.md` — per-game `unshare -Urn` and its
  failure policy.
- `decisions/running-indicator.md` — running records, signal forwarding
  and Terminate.
- `decisions/artwork-provider.md` — why the artwork provider stays
  global instead of gaining a per-game override (reversed 2026-11-05;
  see `decisions/artwork-sources.md`).
- `decisions/artwork-sources.md` — per-game artwork provider, the
  Artwork Source AppID field, local name lookup and the icon fallback
  chain.
- `decisions/artwork-background.md` — the wide backdrop kind, its
  banner fallback and the no-own-download rule.
- `decisions/exe-icon.md` — the icon embedded in a local game's
  executable as the last icon fallback, extracted with `icoextract`.
- `decisions/categories.md` — the persistent category store, the sidebar
  Categories section with icons and counts, the per-category editor, the
  checkable assignment dialog and category normalization.
- `decisions/origin-prefixed-ids.md` — `<origin>-<body>` game IDs, the
  derived Steam AppID and the one-time rename migration.
- `decisions/artwork-cache-keys.md` — canonical artwork cache keys, the
  numeric-name migration and cached art in the Removed games cleanup.
- `decisions/origin-runtime-actions.md` — the origin/runtime context
  menu matrix and the single model table behind it.
- `decisions/graphics-layers.md` — why `[graphics]` stays a plain-Wine
  feature and the runtime build is the version selector.
- `decisions/game-dialog-layout.md` — Details/Execution tabs, the
  manual metadata fields, status badges and the ProtonDB row.
- `decisions/settings-placement.md` — the global Preferences sections,
  the launch-behaviour-only Global Defaults template and the
  per-game-only fields.
- `decisions/external-runtimes.md` — configured-only runtime discovery,
  per-game DXVK/vkd3d version selection and the deferred archive cache.
- `decisions/runtime-manager.md` — the Manage Versions… dialog, the
  per-kind fork repository and manual version deletion.
- `decisions/runtime-archives.md` — latest-release download and safe
  archive extraction for DXVK/vkd3d-proton into the cache dir.
- `decisions/runtime-retention.md` — the three-newest-builds prune, the
  protected builds and why no signature check exists.
- `decisions/download-mirror.md` — the `[ui] download_mirror` prefix, the
  ghproxy URL shape and the digest check through a proxy.
- `decisions/runtime-sources.md` — one list and one default per runtime
  kind, the Wine build list, Proton discovery and the graphics sources.
- `decisions/protondb-local-games.md` — a local game's optional Steam
  store AppID for the ProtonDB rating, and the per-game cache key with
  its recorded target.
- `decisions/metadata-download.md` — the Download Metadata action, the
  fill-empty-only rule, the Steam field mapping and its cache.
