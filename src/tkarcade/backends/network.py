"""Per-game network isolation through unprivileged namespaces (stdlib only).

`unshare -Urn` gives the game a user namespace (so no root is needed) and
a network namespace: inside it there is no route, no DNS and no interface
except a loopback that never comes up. The wrapper is applied innermost,
just around the game, so the pieces that run outside it (Ludusavi
restore/backup, the pre/post hooks) keep their own network.

Kernels or policy modules that forbid unprivileged user namespaces (or a
Flatpak sandbox without the right permission) make the probe fail; the
launcher refuses to start the game in that case rather than quietly
launching it online.
"""

from __future__ import annotations

import functools
import logging
import shutil
import subprocess

log = logging.getLogger("tkarcade.network")

UNSHARE = "unshare"
# -U: user namespace, -r: map the calling user to root inside it, -n:
# network namespace. Together they work without privileges.
UNSHARE_ARGS = (UNSHARE, "-Urn", "--")


@functools.lru_cache(maxsize=1)
def available() -> bool:
    """True when `unshare -Urn` can build the namespace on this machine."""
    if shutil.which(UNSHARE) is None:
        return False
    try:
        proc = subprocess.run(
            [*UNSHARE_ARGS, "true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("network namespace probe failed: %s", e)
        return False
    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip()
        log.warning("network namespace probe failed (rc=%s): %s", proc.returncode, detail)
        return False
    return True


def wrap_command(cmd: list[str], block_internet: bool) -> tuple[list[str], list[str]]:
    """Wrap the game argv so it runs without network. Returns (cmd, warnings)."""
    if not block_internet:
        return cmd, []
    if not available():
        return cmd, [
            "Block Internet is on but unprivileged network namespaces are "
            "unavailable; refusing to launch online"
        ]
    return [*UNSHARE_ARGS, *cmd], []
