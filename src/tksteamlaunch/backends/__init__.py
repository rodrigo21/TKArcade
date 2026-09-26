"""Backend helpers (stdlib only, pure command builders + which checks)."""

from __future__ import annotations

import shlex
import shutil


def which(name: str) -> str | None:
    return shutil.which(name)


def is_flatpak_path(path: str) -> bool:
    return "/flatpak/" in path or path.startswith("/var/lib/flatpak")


def split_args(args: str) -> list[str]:
    args = (args or "").strip()
    if not args:
        return []
    return shlex.split(args)
