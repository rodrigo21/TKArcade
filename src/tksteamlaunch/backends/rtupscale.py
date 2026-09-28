"""linux-rt-upscaler (real-time SRCNN upscaler) wrapper."""

from __future__ import annotations

from . import split_args, which


def apply(cmd: list[str], enable: bool, args: str) -> tuple[list[str], list[str]]:
    """Wrap the game with `upscale -- <game>` (it launches the target)."""
    warnings: list[str] = []
    if not enable:
        return cmd, warnings
    if not which("upscale"):
        return cmd, ["upscale not found, skipping RT upscaler"]
    return ["upscale", *split_args(args), "--", *cmd], warnings
