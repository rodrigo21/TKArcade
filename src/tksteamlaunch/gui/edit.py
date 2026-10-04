"""Standalone settings editor for subprocess use.

The launcher spawns this instead of opening Qt in-process so the dialog
gets a sanitized environment (Steam pollutes LD_LIBRARY_PATH, which
breaks Qt style/theme plugin loading and falls back to Fusion).

Protocol: prints one JSON line {"outcome": ..., "appid": ...} on stdout.
Exit 0 = outcome delivered (launch/saved/cancelled), 2 = unavailable
(no PySide6 or display). Anything else (including tracebacks) means
internal error. Anything on stderr is diagnostic noise the parent logs.

Usage: python -m tksteamlaunch.gui.edit [--appid ID] [--pick]
       [--can-launch | --no-can-launch]
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _ensure_qapp(tool: str) -> bool:
    """Lazy Qt import + display check. False means 'unavailable'."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        print(f"tksteamlaunch: {tool} needs PySide6 installed", file=sys.stderr)
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print(f"tksteamlaunch: {tool} needs a display", file=sys.stderr)
        return False
    return True


def pick_game_appid() -> str:
    """Show a game picker dialog. Returns the AppID or '' when cancelled."""
    from PySide6.QtWidgets import QApplication, QInputDialog

    from .. import config as cfgmod
    from .. import steam as steammod

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    names = {a: n for a, n in steammod.list_games()}
    configured = set(cfgmod.list_appids())
    entries = [(a, names.get(a, a)) for a in configured]
    entries += [(a, n) for a, n in names.items() if a not in configured]
    if not entries:
        return ""
    labels = [f"{n} [{a}]" for a, n in entries]
    choice, ok = QInputDialog.getItem(None, "Edit Game", "Game:", labels, 0, False)
    if not ok or not choice:
        return ""
    for appid, _name in entries:
        if choice.endswith(f"[{appid}]"):
            return appid
    return ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tksteamlaunch.gui.edit")
    p.add_argument("--appid", default="")
    p.add_argument("--pick", action="store_true", help="show a game picker when no AppID is given")
    p.add_argument(
        "--can-launch",
        dest="can_launch",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="hide the launch button when there is no game command to run",
    )
    p.add_argument(
        "--menu",
        action="store_true",
        help="show the Launch / Settings / Cancel menu instead of the editor",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not _ensure_qapp("settings editor"):
        return 2
    from PySide6.QtWidgets import QApplication, QDialog

    from .. import steam as steammod

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    appid = (args.appid or "").strip()
    if not appid and args.pick:
        appid = pick_game_appid()
        if not appid:
            print(json.dumps({"outcome": "cancelled", "appid": ""}))
            return 0
    names = {a: n for a, n in steammod.list_games()}
    if args.menu:
        from .. import config as cfgmod
        from .menu_dialog import MenuDialog

        timeout = 0
        if appid:
            try:
                timeout = cfgmod.load_effective(appid).general.menu_timeout
            except Exception:
                timeout = 0
        dlg = MenuDialog(
            None, appid, names.get(appid, ""), can_launch=args.can_launch, timeout=timeout
        )
    else:
        from .game_dialog import GameDialog

        dlg = GameDialog(
            None, appid, names.get(appid, ""), launch_mode=True, can_launch=args.can_launch
        )
    result = dlg.exec()
    if int(result) != int(QDialog.DialogCode.Accepted):
        outcome = "cancelled"
    else:
        outcome = "launch" if dlg.launch_requested else "saved"
    print(json.dumps({"outcome": outcome, "appid": appid}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
