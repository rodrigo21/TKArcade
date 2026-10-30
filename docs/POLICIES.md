# Project policies (do not regress)

Standing decisions that shape every change. `AGENTS.md` links here.

- No config migration/compat shims (pre-1.0): incompatible configs load
  as fresh built-ins.
- XDG Base Directory for all files; per-game TOML snapshots (full files,
  never sparse); `defaults.toml` is a new-game template only.
- Never write `shortcuts.vdf`: Steam owns
  `userdata/<id>/config/shortcuts.vdf`, and TKArcade writes nothing
  outside its own XDG dirs. A shortcut that still caches
  `tkarcade <old-appid>` fails loudly (exit 10) and is left for the user
  to fix.
- New third-party deps need GPLv3-compatible licenses (MIT/BSD/
  Apache-2.0/PSF/LGPL). External tools via subprocess, never linked.
- Third-party recipes under `packaging/arch/` (linux-rt-upscaler*,
  pyproject-appimage) are synced copies from TKSteamLaunch: check
  drift with `diff -r` against it before tagging, copy the winner
  in a commit of its own.
- Rebuild `-git` locally to verify each batch; its `pkgver` churn
  stays dirty in the tree and out of commits (never `add -A` it; the
  git mechanics are in `docs/GIT.md`). At release time commit the
  current `-git` PKGBUILD with everything else. On a feature branch the
  `-git` source pins that branch; point the pin back at `main` before
  deleting the branch. At release time check every package for new
  versions, update every PKGBUILD and build them all.
- Flatpak Ludusavi cannot see Proton prefixes: always warn, never
  silently accept it.
- Exit codes are part of the CLI contract (10 no AppID, 12 pre-hook,
  13 missing exe, 14 missing prefix/wine/umu-run/Proton runtime, 15 no
  display, 16 import/export, 17 validation issues, 18 environment not set).
  A Steam Linux Runtime that umu has not downloaded yet is **not** an
  exit-14 case: umu fetches it on the first launch, so it is only a hint
  in the dialog and a `(note)` line in `--validate`.
