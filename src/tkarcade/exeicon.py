"""Icon embedded in a Windows executable's resources.

`icoextract` (pure Python, MIT) walks the PE resource tree and returns a
ready `.ico` built from the executable's first icon group, so this module
adds no parser of its own. The import is lazy and every failure means
"no icon": artwork is decoration and must never break a list refresh or a
launch. A build without the dependency simply shows no executable icon.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("tkarcade.exeicon")


def icon_bytes(exe: str | Path | None) -> bytes | None:
    """The executable's first icon group as `.ico` bytes, or None."""
    try:
        path = Path(str(exe or "")).expanduser()
    except (TypeError, ValueError):
        return None
    if not path.name or path.suffix.lower() != ".exe":
        return None
    try:
        if not path.is_file():
            return None
    except OSError:
        return None
    try:
        from icoextract import IconExtractor
    except Exception as e:  # optional dependency: no icon without it
        log.debug("exeicon: icoextract unavailable: %s", e)
        return None
    try:
        return IconExtractor(str(path)).get_icon().getvalue() or None
    except Exception as e:
        log.debug("exeicon: %s: %s", path, e)
        return None
