# TODO — deferred ideas

Where the work stands: `docs/STATE.md` (injected into every session
through `instructions` in `opencode.json`; refresh it with `/handoff`).
This file is the open list only: finished work lives in `CHANGELOG.md`
and git, standing decisions in `docs/POLICIES.md`, and hard-won
QML/toolkit rules in `docs/QML-NOTES.md`. The document map is
`docs/README.md`.

## Deferred research

- [ ] Playnite plugin metadata (Steam/Epic/GOG/PCGW/VNDB) for the local
  library import of Lutris/Playnite/Faugus file formats. The format
  import itself is still pending (only tarball, SteamTinkerLaunch and
  predecessor configs import today); this is the metadata enrichment on
  top of it.
- [ ] Online sources à la Playnite for categories/tags (the per-game
  categories and the drawer filter shipped without them).

## Settings and metadata (sessions ahead)

- [ ] Per-game artwork provider override: the per-game `[artwork]` block
  has no way to override the *provider* for one game (the preference is
  global); decide if a rare mismatched game needs it.
- [ ] Show "Artwork Cleared" in the Artwork Status row: a cleared AppID
  keeps its `"cleared": true` mark in `grids/<appid>.json` with no
  visible trace in the UI — if the art stops coming back and nobody
  remembers the Clear, that file is the answer.
- [ ] Icons and cards views: both views ship; what remains is giving the
  Cover slot a consumer — the card's `Kirigami.Card` banner reads
  `gameIcon`, which falls back to the source AppID's icon, not to the
  cover — and reviewing the card banner framing. `cover` is written,
  cleared and migrated today but nothing renders it. Also: the Status
  row's long text wraps mid-sentence at the 612 px minimum ("…Use Fetch
  / Artwork."), next to a button with the same words.
- [ ] Categories redesign, remaining half: how categories work and how
  they are added. The broken Category column is gone from the library
  list; showing the tags in a right-hand details section waits for that
  section to exist.
- [ ] Per-game metadata fields (all optional), rendered as name suffixes
  in the library list and the other views, never inside the AppID:
  - `version`: free-form for local games; shown as `Name [version]`
    (space before the bracket). On save a trailing `[x]` in the name
    moves into the field: `Jogo Bom [v0.3.5]` → name `Jogo Bom`,
    version `v0.3.5` (the `v` is not required).
  - `date`: `YYYY-MM-DD`, also accepting `YYYY-MM` and `YYYY`
    (Playnite-style, richer than Lutris' year).
  - `tag`: free-form state label, shown as `Name [version] (TAG)`
    with a space before the parenthesis.
  - Applies to Steam and local games; the list column/views layout is
    part of the work.

## Deferred design review

- [ ] **DXVK/vkd3d inside UMU/Proton prefixes.** umu and Steam's Proton
  ship their own DXVK and vkd3d, so `[graphics]` is hidden and ignored
  for them (an old install is only neutralised). Decide whether
  overriding the runtime's versions should be possible at all, how (copy
  into the prefix vs. the runtime's own layer dir), which selector the
  dialog needs, and what happens when Proton updates.
- [ ] **External runtime versions.** Like Lutris, allow several DXVK,
  vkd3d-proton and Proton versions from arbitrary locations, not only
  what is installed system-wide. Audit what `[ui] dxvk_dirs`,
  `vkd3d_dirs` and `proton_dirs` already cover, what is missing (e.g.
  per-game overrides, archives in the cache dir, Steam Linux Runtime
  picks) and how the GUI should present it.
- [ ] Preferences content: decide what is truly global (e.g. Proton/DXVK
  directories, prefix base, SteamGridDB key) versus per-game, and whether
  the window should be split into tabs/sections. The current form mixes
  both and some rows are only meaningful with the tray enabled.
- [ ] Global Defaults content: audit which fields belong in the template.
  Per-game identity/artwork and paths that only make sense for one game
  should not be there.

## Deferred release

Only when the maintainer opens the subject.

- [ ] Release pass: group the `Unreleased` entries, update the `-git`
  PKGBUILD, `diff -r` against TKSteamLaunch, check package versions and
  run `scripts/display-check.sh`. Numbering/tag and signing are the
  maintainer's decision.
- [ ] Re-audit the environment presets against vendor docs on every
  release tag (Mesa/NVIDIA semantics drift; verify `vblank_mode` /
  `__GL_SYNC_TO_VBLANK` values). Last: 2026-10-19 — the vsync pair
  stands against Mesa's current driconf registry (plus the xmlconfig
  env-override test) and the 580.x NVIDIA README; both are
  OpenGL/GLX-only, so Vulkan needs its own present mode and the presets
  carry that in their `note`.
