"""gamemode (Feral) + CachyOS game-performance prefix builders."""
from __future__ import annotations

import logging

from . import which

log = logging.getLogger("tksteamlaunch.gamemode")


def prefix(
    cmd: list[str], feral: bool = False, cachy: bool = False
) -> tuple[list[str], list[str]]:
    """Return (new_cmd, warnings). Outermost order: game-performance, gamemoderun."""
    warnings: list[str] = []
    out = list(cmd)
    if feral:
        if which("gamemoderun"):
            out = ["gamemoderun", *out]
        else:
            warnings.append("gamemoderun not found, skipping Feral GameMode")
    if cachy:
        if which("game-performance"):
            out = ["game-performance", *out]
        else:
            warnings.append("game-performance not found, skipping CachyOS tweak")
    return out, warnings
