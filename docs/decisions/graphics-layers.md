# Graphics layers stay Wine-only

Status: decided (2026-11-01).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: decide whether `[graphics]` (DXVK/vkd3d) should also override the
layers a umu or Proton runtime ships, and if so how.

## Decision

`[graphics]` stays a plain-Wine feature. umu and Proton prefixes never
take the layers, and the game dialog keeps the Graphics section hidden
for them. A runtime's DXVK/vkd3d is chosen by picking a different
runtime build: Steam's per-game compat tool for Steam games, the Proton
entry (`runtime.tool`) for local umu games, and the DXVK/vkd3d
directories for plain Wine as today.

## Why

The installed Proton script (Proton Experimental, 2026-11-01) owns the
DLL search order:

- it sets `WINEDLLPATH` to its own dist first (`lib64/wine/vkd3d`,
  `lib64/wine`) and only appends an inherited value; Wine resolves
  native DLLs through `WINEDLLPATH` before `system32`, so a DLL copied
  into the prefix loses, and a user-prepended path loses to the dist;
- it appends its `WINEDLLOVERRIDES` after the user's, so the runtime's
  overrides win on conflict.

Overriding per game would therefore require replacing files in the
Proton install itself: shared by every game that uses that build,
destroyed by the next Proton update, and out of bounds for a wrapper
(`docs/POLICIES.md` keeps Steam-owned files untouched). The runtime's
DXVK is also the version its patched Wine was tested with; a per-game
swap trades that guarantee for version freedom the user already has by
choosing a build.

## Behaviour today

| Runtime | `[graphics]` |
| --- | --- |
| Local wine | Used: the newest version is copied into the prefix and selected through `WINEDLLOVERRIDES` (`graphics.py`). |
| Local umu | Ignored; an install copied by an older TKArcade is neutralised at launch. |
| Steam (proton or native) | Ignored; the keys are invisible in the dialog. |

## Rejected alternatives

- **Prefix copy for umu/Proton.** Does not work: `WINEDLLPATH` beats
  `system32` (see above).
- **Replace the dist with a backup marker.** Works, but writes into the
  runtime install: shared state, reset by updates, and nothing survives
  a Proton self-update.
- **One Proton copy per game.** Correct but heavy (gigabytes per game)
  and duplicates Steam's own per-game compat-tool selection.
- **Read-only "this runtime ships DXVK x.y".** No decision needs it
  today; picking a build is enough.
