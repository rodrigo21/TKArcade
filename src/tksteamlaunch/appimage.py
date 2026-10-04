"""Unified AppImage entry: settings GUI without launch args, else launcher.

Keeps the launcher path stdlib-only: every import below `sys` is lazy
inside its branch, so game launches never pay for Qt.
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    """Run the GUI (no args or --gui) or the launcher (anything else)."""
    args = sys.argv[1:] if argv is None else argv
    if not args or args == ["--gui"]:
        if argv is None:
            sys.argv = [sys.argv[0]]  # hide --gui from QApplication
        from .gui.app import main as gui_main

        return gui_main()
    from .launcher import main as launcher_main

    return launcher_main() if argv is None else launcher_main(argv)
