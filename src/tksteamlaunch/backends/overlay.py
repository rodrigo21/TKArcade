"""gamescope / mangohud prefix builders."""
from __future__ import annotations

import logging

from . import split_args, which

log = logging.getLogger("tksteamlaunch.overlay")


def apply_mangohud(cmd: list[str], enable: bool, args: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if not enable:
        return cmd, warnings
    if not which("mangohud"):
        return cmd, ["mangohud not found, skipping MangoHud"]
    return ["mangohud", *split_args(args), *cmd], warnings


def apply_gamescope(cmd: list[str], enable: bool, args: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    if not enable:
        return cmd, warnings
    if not which("gamescope"):
        return cmd, ["gamescope not found, skipping gamescope"]
    return ["gamescope", *split_args(args), "--", *cmd], warnings
