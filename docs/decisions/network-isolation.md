# Block Internet per game

Status: implemented (2026-10-23).

Landing record: describes the state when it landed; current behaviour
lives in `README.md`/`CHANGELOG.md` (see `docs/README.md`).

Goal: let one game run without access to the network (single-player
titles, telemetry-heavy launchers) without a root helper, firewall rules
or a new dependency.

## Decisions

**Mechanism.** `unshare -Urn -- <game>`: a user namespace (`-U`, so no
privileges are needed), the caller mapped to root inside it (`-r`, or
file ownership breaks), and a network namespace (`-n`) with only a
loopback interface that is never brought up. Inside, there is no route,
no DNS and no interface to leak through.

**Where it sits.** Innermost, just around the game command, before
MangoHud/GameMode/Gamescope. The Ludusavi wrap (outermost) and the
pre/post hooks keep their own network, so cloud restore/backup and
hooks still work. The game's own process tree (Proton, the game
launcher, its children) inherits the empty namespace.

**Configuration.** `[network] block_internet = true` per game, edited in
Settings → System → Network. The wrapper summary lists "Block Internet"
and the settings hint turns red when the host cannot build the
namespace.

**Failure policy.** If `unshare -Urn` is missing or forbidden (kernel
`kernel.unprivileged_userns_clone=0`, an AppArmor `userns` restriction,
a Flatpak sandbox), the launcher refuses to start the game (exit 14,
"cannot launch") instead of silently launching it online. `--validate`
reports the same issue (exit 17). Launching online despite the explicit
request would defeat the option.

**Probe.** `backends/network.py` runs `unshare -Urn -- true` once per
process and caches the result. The probe is cheap (a fork/exec) and the
cache keeps the settings dialog and the launch path from repeating it.

## Risk matrix

| Area | Behaviour under the namespace |
| --- | --- |
| Multiplayer, achievements, Steam friends, cloud saves | Stop working; expected. |
| Online DRM / always-online launchers | Refuse to start or hang in their own dialog. |
| Loopback-only features (LAN discovery, local web UI) | No interface is up; they fail like a disconnected host. |
| Proton/Wine | Runs; Wine's own IPC uses Unix sockets, not TCP. |
| Anti-cheat / kernel modules | Some refuse to run inside a user namespace; the game reports it itself. |
| Audio (PipeWire/PulseAudio), X11/Wayland, D-Bus | Unaffected: all Unix sockets. |
| Gamescope/MangoHud/GameMode | Unaffected; they are outside the namespace. |
| Hosts with user namespaces disabled | The launcher refuses (exit 14), `--validate` flags it. |

## Out of scope

Selective allowlists (per-host or per-port), DNS filtering, seccomp,
network shaping, and stopping the Steam client's own traffic. The
lighter `WINE_BLOCK_HOSTS` preset remains the option for host-level
blocking that still allows some traffic.

## Tests

- `tests/test_backends.py`: wrapper argv, the off switch, and the
  missing-`unshare` warning (both paths mocked, so the suite does not
  depend on the host's namespace policy).
- `tests/test_launcher.py`: `build_final_command` puts the wrapper
  innermost, `active_wrappers` lists it, and `_final_command` returns 14
  when the host cannot build the namespace.
- `tests/test_config.py`: the key round-trips.
- `tests/test_kirigami_model.py` and `tests/kirigami_qml_cases.py`: the
  Settings checkbox survives a reload/save.
