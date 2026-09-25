"""gamemode (Feral) + CachyOS game-performance prefix builders."""
from __future__ import annotations

from . import which


def prefix(
    cmd: list[str], feral: bool = False, cachy: bool = False
) -> tuple[list[str], list[str]]:
    """Return (new_cmd, warnings). Mutually exclusive: Feral wins on conflict."""
    warnings: list[str] = []
    out = list(cmd)
    if feral and cachy:
        warnings.append(
            "Feral GameMode and CachyOS game-performance are mutually "
            "exclusive; using gamemoderun, ignoring game-performance"
        )
        cachy = False
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
